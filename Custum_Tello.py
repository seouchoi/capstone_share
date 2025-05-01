import socket
import threading
import time
import queue
from Drone_Action import Action

class Tello(Action): #Action클래스를 상속받는 Tello 객체.
    def __init__(self,tello_address : str, port : int, pipe) -> None:
        super().__init__() #상속받는 객체 초기화화
        '''
        tello_address - Tello 드론의 IP 주소 (예: "192.168.0.73")
        port - 내부적으로 바인딩할 포트 번호
        '''
        try:
            self.tello_to_main_pipe = pipe
            self.tello_address = (tello_address, 8889)    # Tello 드론이 명령을 수신하는 주소와 포트
            self.response_que : queue.Queue[str] = queue.Queue(maxsize=3)     # Tello 드론의 응답을 저장할 큐
            self.drone_exit_event : threading.Event = threading.Event()    # 종료 여부를 확인하는 이벤트
            self.socket_tello : socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    # Tello 명령 송신 및 응답 수신용 소켓
            self.socket_tello.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)     # 소켓 재사용 옵션 설정
            self.socket_tello.bind(("0.0.0.0",port))    # Tello 명령 수신 소켓 바인딩
            self.response_thread = threading.Thread(target = self.receive_response)    # Tello로부터 명령 응답을 받아오는 스레드
            self.response_thread.daemon = True
        except Exception as e:
            print(e)


    def connect(self) -> bool:    # Tello 드론과 연결 시도 함수
        self.response_thread.start()     # 드론 응답 수신 스레드 시작
        time.sleep(1)
        if self.connect_drone():
            return True
        return False
            
    
    def receive_response(self) -> None:    #드론 소켓으로부터 응답을 수신하는 함수
        try:
            while True:
                data, server = self.socket_tello.recvfrom(1518)     # 소켓에서 데이터를 읽어 큐에 저장
                self.response_que.put(str(data.decode(encoding="UTF-8")))
        except Exception as e:
            print(e)
                
            
    def get_response(self) -> str:    #드론으로부터 받은 응답을 큐에서 꺼내 반환하는 함수
        try:
            msg : str = self.response_que.get_nowait()
            return msg
        except queue.Empty:
            return ''
    
    
    def connect_drone(self) -> bool:    #드론과 명령 모드로 연결을 시도하는 함수
        try:
            for i in range(3):   #command' 명령을 최대 세 번 재전송
                self.socket_tello.sendto('command'.encode('utf-8'),self.tello_address)
                time.sleep(3)
                s = self.get_response()
                if s == 'ok':
                    return True
            return False
        except Exception as e:
            print(e)
            return False
      