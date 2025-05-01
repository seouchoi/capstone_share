import socket
import av
from typing import List
import threading
import queue
from Detection_Pipeline import DetectionPipeline

class VideoReceiver:
    def __init__(self, tello_address: List[str], pipe) -> None:
        self.video_to_main_pipe = pipe
        self.tello_address = tello_address
        self.video_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.video_socket.bind(("0.0.0.0", 11111))
        self.packet_queues = {ip: queue.Queue(maxsize=5) for ip in self.tello_address}
        self.detection_pipeline = DetectionPipeline()
        
    def video_reciver(self) -> None:
        try:
            while True:
                data, (src_ip, _) = self.video_socket.recvfrom(2048)
                if src_ip in self.packet_queues:
                    q = self.packet_queues[src_ip]
                    if q.full():
                        try:
                            q.get_nowait()
                        except queue.Empty:
                            pass
                    q.put_nowait(data)
        except Exception as e:
            print(f"[Receiver Error] {e}")
            
            
    def decoder_worker(self, ip: str) -> None:
        codec = av.CodecContext.create("h264", "r")
        buffer = b""

        try:
            while True:
                pkt_data = self.packet_queues[ip].get()
                buffer += pkt_data

                # 작은 패킷이 들어오면 프레임이 끝났다는 뜻
                if len(pkt_data) < 1460:
                    try:
                        packet = av.packet.Packet(buffer)
                        frames = codec.decode(packet)
                        for frame in frames:
                            img = frame.to_ndarray(format="bgr24")
                            self.detection_pipeline.process_frame(img, ip)
                    except Exception as decode_err:
                        print(f"[Decode Fail @ {ip}] {decode_err}")
                    buffer = b""  # 다음 프레임 준비

        except Exception as e:
            print(f"[Decoder {ip} Error] {e}")




    def vid_main(self) -> None:
        threads: List[threading.Thread] = []
        recv_thread = threading.Thread(target=self.video_reciver)
        recv_thread.start()
        threads.append(recv_thread)
        for ip in self.tello_address:
            dec_thread = threading.Thread(target=self.decoder_worker, args=(ip,))
            dec_thread.start()
            threads.append(dec_thread)
        try:
            for t in threads:
                t.join()
        except Exception as e:
            print(f"[Main Error] {e}")

