import socket
import pickle
import struct
import threading
import time
from typing import Any, Dict, Optional, Union
from multiprocessing.sharedctypes import SynchronizedArray

class GcsConnector:
    def __init__(self, gcs_to_main_pipe: Any, main_to_video_pipe : Any, drone_location_array : SynchronizedArray, tello_location_array : SynchronizedArray, gcs_ip: str = '192.168.0.101', gcs_port: int = 5270, reconnect_delay: Union[int, float] = 5) -> None:
        self.gcs_pipe = gcs_to_main_pipe
        self.video_pipe = main_to_video_pipe
        self.gcs_ip: str = gcs_ip
        self.gcs_port: int = gcs_port
        self.reconnect_delay: Union[int, float] = reconnect_delay
        self.lock = threading.Lock()
        self.socket: Optional[socket.socket] = None
        self.cancel_event = threading.Event()
        self.drone_location_array : SynchronizedArray = drone_location_array #드론 위치 배열 
        self.tello_location_array : SynchronizedArray = tello_location_array
        self.connect()
        self.recv_data_thread = threading.Thread(target=self.recv_data, daemon=True)
        self.send_location_data_thread = threading.Thread(target=self.send_location_data, daemon=True)


    def connect(self) -> None:
        while not self.cancel_event.is_set():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10)
                sock.connect((self.gcs_ip, self.gcs_port))
                sock.settimeout(None)
                self.socket = sock
                #self.send_data(message='check', data={})
                return
            except Exception as e:
                print(f"Connection failed: {e}")
                time.sleep(self.reconnect_delay)


    def close(self) -> None:
        self.cancel_event.set()
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            finally:
                self.socket = None


    def send_data(self, data: Dict = {}, message: str = '') -> None:
        packet = pickle.dumps({'message': message, 'data': data})
        with self.lock:
            try:
                if self.socket:
                    self.socket.sendall(packet)
            except Exception as e:
                print(f"Send failed: {e}")
                self.socket = None
                self.connect()


    def recv_data(self) :
        try:
            while True:
                data_byte = self.socket.recv(1024)
                data : Dict = pickle.loads(data_byte)
                try:
                    self.gcs_pipe.send(data)
                except Exception as e:
                    print("Error sending data to main process:", e)
                    break
        except Exception as e :
            print(f"Receive failed: {e}")
            self.close()
            
            
    def send_location_data(self) -> None:
        try:
            while True:
                detection = ''
                if self.video_pipe.poll():
                    detection = self.video_pipe.recv()
                with self.drone_location_array.get_lock():  
                    drone_location = list(self.drone_location_array)
                with self.tello_location_array.get_lock():
                    tello_location = list(self.tello_location_array)
                data : Dict = {
                    'detection' : detection,
                    'drone_location' : drone_location,
                    'tello_location' : tello_location
                }
                self.send_data(message='l', data= data)
                time.sleep(0.1)
        except Exception as e:
            print(f"error send_location_data : {e}")


    def start(self) -> None:
        self.recv_data_thread.start()
        self.send_location_data_thread.start()