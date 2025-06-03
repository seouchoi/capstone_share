from ultralytics import YOLO
import numpy as np
import cv2

class YoloImageDetector:
    def __init__(self, model_path="rand2.pt"):
        self.model = YOLO(model_path) #훈련된 모델을 로드함.
        self.sessions = {} # IP별 세션 상태를 저장하는 딕셔너리


    def ensure_session(self, ip):
        # 특정 IP에 대한 세션이 없으면 새로 생성
        if ip not in self.sessions:
            self.sessions[ip] = {
                'dic': {}, # 객체 ID별 박스, 누적 카운트, 시간 정보 저장
                'count': 1 # 새 객체에 부여할 고유 ID 번호
            }
            
            
    def cleanup(self, ip_address, max_age=30):
        # 일정 시간 이상 지난 객체 정보를 세션에서 제거
        dic = self.sessions[ip_address]['dic']
        to_del = [k for k, v in dic.items() if v[2] >= max_age]
        for k in to_del:
            del dic[k]
            

    def detect_dic(self, box, fall, ip_address):
        """
        - box: 현재 탐지된 객체의 중심 좌표 (x, y)
        - fall: 클래스 값 (낙상 여부 등으로 추정)
        - return: (누적 카운트 값, 객체 ID)
        """
        session = self.sessions[ip_address]
        dic = session['dic']
        cnt = session['count']
        if not dic:
            # 최초 객체 → 새로운 ID 부여
            dic[cnt] = np.array([box, 0, 0], dtype=object) # [좌표, 탐지 객체, 프레임 생존 시간]
            session['count'] += 1
            return 0, 0
        indices = list(dic.keys())
        coords = np.array([v[0] for v in dic.values()], dtype=float)
        dists = np.linalg.norm(coords - box, axis=1) # 기존 객체들과의 거리 계산
        nearest_id = indices[np.argmin(dists)]
        if np.min(dists) < 50:
            # 가까운 기존 객체로 판단 → 상태 갱신
            rec = dic[nearest_id]
            rec[1] = np.clip(rec[1] + (1 if fall else -1), 0, 2) # 낙상 누적 카운트 조정
            rec[2] = max(rec[2] - 1, 0) # 생존 시간 감소
            return rec[1], nearest_id
        else:
            # 새 객체로 판단 → 새로운 ID 부여
            dic[cnt] = np.array([box, 0, 0], dtype=object)
            session['count'] += 1
            return 0, 0


    def predict_image(self, image : np.ndarray, ip_address):
        # 프레임 복사 및 디버그용 화면 출력
        frame = image.copy()
        cv2.imshow("a", frame)
        cv2.waitKey(1)
        self.ensure_session(ip_address) # 세션 준비
        dic = self.sessions[ip_address]['dic']
        for rec in dic.values():
            rec[2] += 1 # 프레임 생존 시간 증가 (cleanup 기준에 사용됨)
        result = self.model.predict(
            frame,
            iou=0.1, # IOU 임계값 (겹침 판단 기준 낮게 설정)
            half=True, # FP16 모드 사용 (속도 향상)
            conf=0.3, # Confidence threshold
            verbose=False,
            device=0 # GPU 0번 사용
        )
        boxes = result[0].boxes.cpu().numpy()
        num = boxes.cls.size # 탐지된 객체 수

        if num == 0:
            self.cleanup(ip_address) # 아무것도 탐지 안 됐으면 세션 정리
            return 0, 0, 0
        
        # 클래스(label)과 중심 좌표 (xywh) 추출
        classes = boxes.cls.astype(int) # 클래스 인덱스 (ex. 낙상 여부)
        xywh = boxes.xywh[:, :2].astype(int) # 중심좌표 (x, y)

        for i in range(num):
            # 개별 객체에 대해 추적 및 상태 판단
            move_stack, obj_id = self.detect_dic(xywh[i], classes[i], ip_address)
            if move_stack == 6:
                # 낙상 누적이 6회 이상이면 감지 완료로 판단
                x, y = int(xywh[i][0]), int(xywh[i][1])
                self.cleanup(ip_address) # 현재 프레임에서 세션 정리
                return x, y, 1# 감지 종료

        self.cleanup(ip_address) # 루프가 끝난 후도 세션 정리
        return 0, 0, 0

