from typing import List, Dict, Tuple, Any
import threading
import time


class Commander:
    def __init__(self,tello_info: Dict, main_to_tello_pipes: Dict) -> None:
        self.tello_info : Dict = tello_info #tello 정보가 들어가있는 딕셔너리
        self.main_to_tello_pipes : Dict = main_to_tello_pipes #main쪽에 연결돼어있는 파이프(tello와 연결결)
        self.death_drone : List = [] #죽은 드론을 저장하는 리스트
        self.tello_command : dict = {} #드론에 대한 명령을 저장하는 딕셔너리
        for name in tello_info.keys():
            self.tello_command[name] = '' #각 드론에 대한 명령을 저장하기 위한 딕셔너리      
        self.readjust : bool = False #위치 재조정 여부
        
        
    def is_alive(self, name :str , pipe : Any) -> bool:
        if name not in self.death_drone:
            pipe.send(("get_battery", (), {}))
            respone : Tuple = self.wait_for_respone(pipe, 1.1)
            if respone[1] == 'timeout' or respone[1] == 'error':
                self.death_drone.append(name)
                return False
            else:
                return True
        return False
            
    
    def wait_for_respone(self, pipe: Any, wait_time: float = 1.0) -> Tuple:
        if pipe.poll(wait_time):
            response : Tuple = pipe.recv()
            return response
        else:
            return ('', 'timeout') 

    #아래와 같은 형식으로 명령을 주면됨.(Action class에서 제대로 만들어져야함.)
    def situation_1(self, name : str, pipe : Any) -> None:
        print(f"{name} situation_1 호출")
        pipe.send(("double_sin_wave", (), {})) 
        
        
    def situation_2(self, death : str, name : str, pipe : Any) -> None:
        """드론 한 대 사망 시: 생존 드론 재배치 후 솔로 웨이브"""
        survivor = "tello1" if death == "tello0" else "tello0"

        if not self.readjust:
            # 1) 위치 재조정 명령 전송
            pipe.send(("readjust_position", (), {"side": survivor}))
            # 2) readjust 완료 ACK 대기 (최대 5 s)
            if pipe.poll(5.0):
                _ = pipe.recv()
            self.readjust = True

        # 3) 솔로 사인웨이브 시작
        pipe.send(("solo_sin_wave", (), {"side": survivor}))

    #처음은 드론 두 대만 사용할 것이므로 드론이 2개 일 때, 1개 일 때만 상황이 주어짐
    # def situation_3(self):
    #     pass
        
    #드론이 모두 살아있으면 sit_1, 하나만 살아있으면 sit_2
    #여기서 situation을 반복문을 계속 돌려서 drone_count가 줄어들면 그게 맞게 행동을 바꾸도록 해야함.
    #함수를 비동기로 만들어서 하던지, 또는 메인 프로세스에서 스레드를 하나 만들어서 commander용으로 할건지 결정해야함.
    
    def command_thread(self, name : str, pipe : Any) -> None:
        takeoff : bool = False
        while True:
            state : bool = self.is_alive(name, pipe)
            print(f"{name} state: {state}")
            if state:
                if self.tello_command[name] != '':
                    print(f"{name} command: {self.tello_command[name]}")
                    pipe.send((self.tello_command[name], (), {}))
                    response : Tuple = self.wait_for_respone(pipe, 12)
                    print(f"{name} response: {response}")
                    self.tello_command[name] = ''
                    if response[0] == 'takeoff' and response[1] == 'ok':
                        takeoff = True
                    time.sleep(3)
                    continue
                elif takeoff:
                    if self.death_drone == []:
                        self.situation_1(name, pipe)
                    else:
                        self.situation_2(self.death_drone[0],name, pipe)
                    response : Tuple = self.wait_for_respone(pipe, 30)
                    if response[1] == 'timeout' or response[1] == 'error':
                        print(f"{name} response: {response}")
                        self.death_drone.append(name)
                        return
            else:
                return            
            
    
    def start(self) -> None:
        Commander_thread : List = []
        for tello_name in self.tello_info.keys():
            print(self.main_to_tello_pipes)
            print(tello_name)
            tello_command_thread : threading.Thread = threading.Thread(target=self.command_thread, args=(tello_name, self.main_to_tello_pipes[tello_name]), daemon=True)
            Commander_thread.append(tello_command_thread) #각 드론에 대한 스레드를 추가함
            tello_command_thread.start()
        # 드론이 모두 살아있을 때까지 대기
        #for thread in Commander_thread:
        #    thread.join()
                