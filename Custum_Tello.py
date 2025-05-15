import socket
import threading
import time
import queue
from Tello_Action import Action
from typing import Any, Dict, List, Tuple, Union
import math


class Tello(Action): #Action클래스를 상속받는 Tello 객체.
    def __init__(self, name : str, tello_address : str, port : int, pipe : Any, drone_location_array : Any, drone_location_lock : Any) -> None:
        super().__init__() #상속받는 객체 초기화화
        '''
        tello_address - Tello 드론의 IP 주소 (예: "192.168.0.73")
        port - 내부적으로 바인딩할 포트 번호
        '''
        try:
            self.name = name #드론 이름
            self.init_distance =100 #드론의 초기 거리
            self.drone_distance_offset = 200 #드론과의 거리
            self.tello_to_main_pipe = pipe #tello 입출력 파이프(main과 연결결)
            self.tello_address = (tello_address, 8889)    # Tello 드론이 명령을 수신하는 주소와 포트
            self.response_que : queue.Queue[str] = queue.Queue(maxsize=3)     # Tello 드론의 응답을 저장할 큐
            self.drone_exit_event : threading.Event = threading.Event()    # 종료 여부를 확인하는 이벤트
            self.socket_tello : socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    # Tello 명령 송신 및 응답 수신용 소켓
            self.socket_tello.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)     # 소켓 재사용 옵션 설정
            self.socket_tello.bind(("0.0.0.0",port))    # Tello 명령 수신 소켓 바인딩
            self.response_thread = threading.Thread(target = self.receive_response)    # Tello로부터 명령 응답을 받아오는 스레드
            self.response_thread.daemon = True
            self.drone_locaion_Array = drone_location_array #드론 위치를 저장할 배열 
            self.drone_location_lock = drone_location_lock #드론 위치를 저장할 배열에 대한 락
            self.init_yaw : List = [0, 0]
            self.tello_state : Dict ={
                "battery" : 0, #드론의 배터리 잔량
                "height" : 0, #드론의 높이
                "yaw" : 0, #드론의 yaw
                "location" : [0, 0], #드론의 위치
            }
            self.latest_time : float = 0.0 #드론의 최신 시간
            self.tello_params : Dict = {
                "init_distance" : -self.init_distance if self.name == 'tello0' else self.init_distance, #드론의 초기 거리
                "side" : 0 if self.name == 'tello0' else 1, #드론의 방향
                "cycle_distance" : 100, #드론이 이동하는 거리
                "kp_pos" : 0.5, #드론의 위치를 보정하는 비율
                "kp_yaw" : 0.5, #드론의 yaw를 보정하는 비율
                "DT" : 0.1, #제어 주기
                "threshold" : 20, #드론의 위치 오차
            }
            self.tello_params["drone_distance_offset"] = (-self.drone_distance_offset if self.name == 'tello0' else self.drone_distance_offset) - self.tello_params["init_distance"] #드론과의 거리리
        except Exception as e:
            print(e)
            
        
    def get_drone_location(self) -> List[float]:    #드론의 위치를 반환하는 함수
        with self.drone_location_lock:    #드론 위치를 저장할 배열에 대한 락을 걸어줌.
            drone_location = list(self.drone_locaion_Array) #드론 위치를 저장할 배열을 복사함.
        drone_location[0] = drone_location[0] + 300 #드론 위치의 x좌표를 300만큼 더해줌.
        drone_location[1] = drone_location[1] + self.tello_params["drone_distance_offset"] #드론 위치의 y좌표를 초기 거리만큼 더해줌.
        return drone_location #드론 위치를 반환함.


    def set_init_state(self) -> None:    #드론의 초기 상태를 설정하는 함수
        self.update_state() #드론의 상태를 업데이트함.
        init_location = self.get_drone_location()
        self.init_yaw[0] = self.tello_state["yaw"] #드론의 yaw를 초기 yaw로 설정함.
        self.init_yaw[1] = init_location[2] #드론의 yaw를 초기 yaw로 설정함.
        
  
    def compute_control(self, target_location: List[float]) -> Tuple[float, float, float, float]:
        pass
        #return vx, vy, yaw_vel, dist
    
    
    def update_position(self, vx, vy) -> None:    #드론의 위치를 업데이트하는 함수
        self.tello_state["location"] += vx * self.tello_params["DT"]
        self.tello_state["location"] += vy * self.tello_params["DT"]

    
    def cycile(self) -> None:    #드론의 위치를 업데이트하는 함수
        now = time.time()
        if now - self.latest_time < self.tello_params["DT"]:
            time.sleep(self.tello_params["DT"] - (now - self.latest_time))
        self.latest_time = time.time()
        self.update_state() #드론의 상태를 업데이트함.
        target_location = self.get_drone_location() #드론의 위치를 가져옴.
        vx, vy, yaw_vel, dist = self.compute_control(target_location) #드론의 위치를 업데이트함.
        self.rc(int(vx), int(vy), 0, int(yaw_vel)) #드론의 속도를 업데이트함.
        
        if dist < self.tello_params["threshold"]:
            self.tello_params["side"] = (self.tello_params["side"] + 1) % 3 #드론의 방향을 바꿈.

    
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
                
            
    def get_response(self, wait : int = 0) -> str:    #드론으로부터 받은 응답을 큐에서 꺼내 반환하는 함수
        if wait == -1: #wait이 -1이라면 응답을 기다리지 않고 바로 반환
            return 'ok'
        try:
            msg : str = self.response_que.get(timeout=wait)
            return msg
        except queue.Empty:
            return 'error'
        
        
    def empty_response(self) -> None:    #응답 큐를 비우는 함수
        while not self.response_que.empty():
            try:
                self.response_que.get_nowait()
            except queue.Empty:
                break
    
    
    def connect_drone(self) -> bool:    #드론과 명령 모드로 연결을 시도하는 함수
        try:
            for _ in range(3):   #command' 명령을 최대 세 번 재전송
                s = self.command()
                if s == 'ok': #ok라는 응답이 온다면
                    self.streamon()
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