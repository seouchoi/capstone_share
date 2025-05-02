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
            self.tello_to_main_pipe = pipe #tello 입출력 파이프(main과 연결결)
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
        if self.connect_drone(): #드론과 연결
            return True
        return False
            
    
    def receive_response(self) -> None:    #드론 소켓으로부터 응답을 수신하는 함수
        try:
            while True:
                data, server = self.socket_tello.recvfrom(1518)     # 소켓에서 데이터를 읽어 큐에 저장
                self.response_que.put(str(data.decode(encoding="UTF-8"))) #응답을 받아서 응답 큐에 저장
        except Exception as e:
            print(e)
                
            
    def get_response(self) -> str:    #드론으로부터 받은 응답을 큐에서 꺼내 반환하는 함수
        try:
            msg : str = self.response_que.get_nowait() #응답을 큐에서 꺼냄냄
            return msg
        except queue.Empty:
            return ''
    
    
    def connect_drone(self) -> bool:    #드론과 명령 모드로 연결을 시도하는 함수
        try:
            for i in range(3):   #command' 명령을 최대 세 번 재전송
                self.socket_tello.sendto('command'.encode('utf-8'),self.tello_address) #드론에게 command를 보냄
                time.sleep(3)
                s = self.get_response() #응답을 받음
                if s == 'ok': #ok라는 응답이 온다면
                    self.socket_tello.sendto('streamon'.encode('utf-8'),self.tello_address) #streamon 명령을 보내서 비디오를 실행함.
                    return True
            return False
        except Exception as e:
            print(e)
            return False
      
    def tello_control(self): #이 함수는 commander 객체(메인프로세스)에서 파이프로부터 받아온 메세지를 실행하는 부분임.(계속해서 명령을 수행할 부분) 
        while True:
            if self.tello_to_main_pipe.poll(): #파이프로부터 받아진 메세지가 있는지 확인
                func_name, args, kwargs = self.tello_to_main_pipe.recv() #응답을 받음. 목적은 Tello_Action에서 tello.forward()처럼 함수형식으로 부르기 위해 만듦.
                try:
                    func = getattr(self, func_name) #self(tello 객체)에서 func_name의 동작을 하도록 함. ex)tello.forward(), tello.takeoff()
                    func(*args, **kwargs) #함수를 실행할 때 인자를 받는 부분. 
                    print(f"[{self.tello_address}] {func_name} 실행됨")
                except Exception as e:
                    print(f"[{self.tello_address}] {func_name} 실행 오류: {e}")        