from ultralytics import YOLO
import numpy as np
import cv2

class YoloImageDetector:
    def __init__(self, model_path=r"C:\Users\hi034\OneDrive\바탕 화면\캡스톤 프로젝트\drone\rand2.pt"):
        self.model = YOLO(model_path)
        self.sessions = {}


    def ensure_session(self, ip):
        if ip not in self.sessions:
            self.sessions[ip] = {
                'dic': {},
                'count': 1
            }
            
            
    def cleanup(self, ip_address, max_age=30):
        dic = self.sessions[ip_address]['dic']
        to_del = [k for k, v in dic.items() if v[2] >= max_age]
        for k in to_del:
            del dic[k]
            

    def detect_dic(self, box, fall, ip_address):
        session = self.sessions[ip_address]
        dic = session['dic']
        cnt = session['count']
        if not dic:
            dic[cnt] = np.array([box, 0, 0], dtype=object)
            session['count'] += 1
            return 0, 0
        indices = list(dic.keys())
        coords = np.array([v[0] for v in dic.values()], dtype=float)
        dists = np.linalg.norm(coords - box, axis=1)
        nearest_id = indices[np.argmin(dists)]
        if np.min(dists) < 50:
            rec = dic[nearest_id]
            rec[1] = np.clip(rec[1] + (1 if fall else -1), 0, 2)
            rec[2] = max(rec[2] - 1, 0)
            return rec[1], nearest_id
        else:
            dic[cnt] = np.array([box, 0, 0], dtype=object)
            session['count'] += 1
            return 0, 0


    def predict_image(self, image : np.ndarray, ip_address):
        frame = image.copy()
        cv2.imshow("a", frame)
        cv2.waitKey(1)
        self.ensure_session(ip_address)
        dic = self.sessions[ip_address]['dic']
        for rec in dic.values():
            rec[2] += 1
        result = self.model.predict(
            frame,
            iou=0.1,
            half=True,
            conf=0.3,
            verbose=False,
            device=0
        )
        boxes = result[0].boxes.cpu().numpy()
        num = boxes.cls.size

        if num == 0:
            self.cleanup(ip_address)
            return

        classes = boxes.cls.astype(int)
        xywh = boxes.xywh[:, :2].astype(int)

        for i in range(num):
            move_stack, obj_id = self.detect_dic(xywh[i], classes[i], ip_address)
            if move_stack == 6:
                x, y = int(xywh[i][0]), int(xywh[i][1])
                self.cleanup(ip_address)
                return

        self.cleanup(ip_address)
        return

