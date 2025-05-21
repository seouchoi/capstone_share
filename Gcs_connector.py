import socket
import pickle
import struct
import threading
import time
from typing import Any, Dict, Optional, Union


class GcsConnector:
    def __init__(self, pipe: Any, gcs_ip: str = '192.168.0.18', gcs_port: int = 5270, reconnect_delay: Union[int, float] = 5) -> None:
        self.pipe = pipe
        self.gcs_ip: str = gcs_ip
        self.gcs_port: int = gcs_port
        self.reconnect_delay: Union[int, float] = reconnect_delay
        self.lock = threading.Lock()
        self.socket: Optional[socket.socket] = None
        self.cancel_event = threading.Event()
        self.connect()


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


    def send_data(self, data: Dict[str, Any] = {}, message: str = '') -> None:
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
                    self.pipe.send(data)
                except Exception as e:
                    print("Error sending data to main process:", e)
                    break
        except Exception as e :
            print(f"Receive failed: {e}")
            self.close()
            

    def start(self) -> None:
        thread = threading.Thread(target=self.recv_data, daemon=True)
        thread.start()
