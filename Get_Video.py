import socket
import av
from typing import List
import threading
import queue
from Detection_Pipeline import DetectionPipeline

class VideoReceiver:
    def __init__(self, tello_address: List[str], pipe) -> None:
        self.video_to_main_pipe = pipe #video 프로세스의 입출력 파이프(main과 연결)
        self.tello_address = tello_address #tello 주소(ip식별)
        self.video_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP 비디오 수신용 소켓 생성
        self.video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # 포트를 재사용할 수 있도록 설정 (빠른 재시작을 위해 필요)
        self.video_socket.bind(("0.0.0.0", 11111)) # 모든 IP로부터 수신 가능하도록 11111 포트에 바인딩 (Tello의 비디오 스트림 기본 포트)
        self.packet_queues = {ip: queue.Queue(maxsize=5) for ip in self.tello_address} # 각 Tello 드론의 IP에 대한 비디오 패킷 큐 생성 (최대 5개까지 버퍼링)
        self.detection_pipeline = DetectionPipeline() # 영상 처리 파이프라인 객체 초기화 (예: 객체 탐지, YOLO 등)
        
    def video_reciver(self) -> None:
        try:
            while True:
                data, (src_ip, _) = self.video_socket.recvfrom(2048) # 소켓으로부터 최대 2048바이트 크기의 비디오 패킷 수신
                if src_ip in self.packet_queues: # 수신한 IP가 등록된 드론 주소 목록에 있는 경우만 처리
                    q = self.packet_queues[src_ip]
                    if q.full(): # 큐가 가득 차면
                        try:
                            q.get_nowait()  #가장 오래된 패킷 제거 (frame drop)
                        except queue.Empty:
                            pass
                    q.put_nowait(data) # 수신한 새 비디오 패킷을 큐에 추가
        except Exception as e:
            print(f"[Receiver Error] {e}")
            
            
    def decoder_worker(self, ip: str) -> None:
        codec = av.CodecContext.create("h264", "r") # H.264 비디오 코덱 디코더를 생성 (읽기 모드 'r')
        buffer = b"" # 버퍼를 초기화 (수신된 패킷을 임시 저장)

        try:
            while True:
                pkt_data = self.packet_queues[ip].get() # 지정된 IP에 해당하는 패킷 큐에서 하나의 패킷을 가져옴 (blocking)
                buffer += pkt_data # 기존 버퍼에 새로 받은 패킷 데이터를 추가

                # 작은 패킷이 들어오면 프레임이 끝났다는 뜻
                if len(pkt_data) < 1460:
                    try:
                        packet = av.packet.Packet(buffer) # 하나의 완성된 패킷을 PyAV 패킷 객체로 생성
                        frames = codec.decode(packet) # 디코더로부터 프레임을 디코딩
                        for frame in frames:
                            img = frame.to_ndarray(format="bgr24") # 프레임을 NumPy 배열(BGR24 포맷)로 변환
                            self.detection_pipeline.process_frame(img, ip) # 디텍션 파이프라인으로 이미지와 IP를 넘김
                    except Exception as decode_err: 
                        print(f"[Decode Fail @ {ip}] {decode_err}")
                    buffer = b""  # 다음 프레임 준비

        except Exception as e:
            print(f"[Decoder {ip} Error] {e}")




    def vid_main(self) -> None:
        threads: List[threading.Thread] = [] # 스레드를 저장할 리스트 초기화
        
        # 1. 영상 수신 스레드 생성 및 시작
        recv_thread = threading.Thread(target=self.video_reciver)  # video_reciver는 각 드론으로부터 UDP로 영상 데이터를 수신
        recv_thread.start()
        threads.append(recv_thread)
        
        # 2. 각 드론 IP별 디코더 스레드 생성 및 시작
        for ip in self.tello_address:
            dec_thread = threading.Thread(target=self.decoder_worker, args=(ip,)) # decoder_worker는 해당 IP의 패킷 큐를 받아 H.264 프레임으로 디코딩
            dec_thread.start()
            threads.append(dec_thread)
        try:
            # 3. 모든 스레드가 종료될 때까지 대기 (영상 수신 + 디코더들)
            for t in threads:
                t.join()
        except Exception as e:
            print(f"[Main Error] {e}")

