import socket
import cv2
from typing import Set, List
import multiprocessing
import threading
import time
import queue

class Tello:
    def __init__(self,tello_address : str) -> None:
        try:
            self.tello_address = (tello_address, 8889)
            self.state_port : int = 8890
            self.dron_state : str = ''    #드론의 상태를 나타내는 변수
            self.response_que : queue.Queue[str] = queue.Queue(maxsize=3)
            self.drone_exit_event : threading.Event = threading.Event()
            self.socket_tello : socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket_state : socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket_tello.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket_state.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket_tello.bind(("0.0.0.0",9000))
            self.response_thread = threading.Thread(target = self.receive_response)
            self.response_thread.daemon = True
            
            #self.video=cv2.VideoCapture("udp://@0.0.0.0:11111")
        except Exception as e:
            print(e)


    def connect(self) -> bool:
        self.response_thread.start()
        time.sleep(1)
        if self.connect_drone():
            return True
        return False
            
    
    def receive_response(self) -> None:
        try:
            while True:
                data, server = self.socket_tello.recvfrom(1518)
                self.response_que.put(str(data.decode(encoding="UTF-8")))
        except Exception as e:
            print(e)
                
            
    def get_response(self) -> str:
        try:
            msg : str = self.response_que.get_nowait()
            return msg
        except queue.Empty:
            return ''
    
    
    def connect_drone(self) -> bool:
        try:
            for i in range(3):
                self.socket_tello.sendto('command'.encode('utf-8'),self.tello_address)
                time.sleep(0.5)
                s = self.get_response()
                print(s)
                if s == 'ok':
                    return True
            return False
        except Exception as e:
            print(e)
            return False
        
        
    def state_stream_on(self) :
        try:
            self.socket_state.bind(("0.0.0.0",self.state_port))
            return self.socket_state
        except Exception as e:
            print(e)
           
        
    def send_command(self,msg) -> bool:
        try:
            self.socket_tello.sendto(msg.encode('utf-8'),self.tello_address)
            return True
        except Exception as e:
            print(e)
            return False
        
def rec (socket_state):
    while True:
        data, server = socket_state.recvfrom(1518)
        print(data.decode(encoding="UTF-8"))
        
t = Tello('192.168.0.73')

if t.connect():
    time.sleep(5)
    socket_state = t.state_stream_on()
    commander_process = multiprocessing.Process(target = rec,args=(socket_state,))
    commander_process.start()
    time.sleep(100)
    