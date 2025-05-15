from typing import List
import threading

class Commander:
    def __init__(self,tello_info: dict, main_to_tello_pipes: dict):
        self.tello_info = tello_info #tello 정보가 들어가있는 딕셔너리
        self.main_to_tello_pipes = main_to_tello_pipes #main쪽에 연결돼어있는 파이프(tello와 연결결)
        self.death_drone = [] #죽은 드론을 저장하는 리스트
        self.tello_command : dict = {} #드론에 대한 명령을 저장하는 딕셔너리
        for i, (name, (ip, port)) in enumerate(tello_info.items()):
            self.tello_command[name] = '' #각 드론에 대한 명령을 저장하기 위한 딕셔너리      
        self.readjust = False #위치 재조정 여부
        
    def is_alive(self, name, pipe) -> bool:
        if name not in self.death_drone:
            print("is_alive 호출")
            pipe.send(("get_battery", (), {}))
            if not pipe.poll(0.1):
                self.death_drone.append(name)
                return False
            else:
                _ = pipe.recv()
        return True

        
    #아래와 같은 형식으로 명령을 주면됨.(Action class에서 제대로 만들어져야함.)
    def situation_1(self,pipe, name) -> None:
        #쌈뽕하게 작성한 부분(효율은 좋지만 가독성 구림)
        #실험용
        print("situation_1 호출")
        pipe.send(("double_sin_wave", (), {"side": name})) 
        
    def situation_2(self, death: str, pipe) -> None:
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
    
    def command_thread(self, name, pipe) -> None:
        while True:
            state : bool = self.is_alive(name, pipe)
            if state:
                if self.tello_command[name] != '':
                    pipe.send(self.tello_command[name])
                    self.tello_command[name] = ''
                elif self.death_drone == []:
                    self.situation_1(pipe, name)
                else:
                    self.situation_2(self.death_drone[0],pipe)
                pass
            else:
                self.death_drone.append(name)
                break
            '''
            if pipe.poll(10): #10초 이내에 응답이 오면
                response = pipe.recv()
            else:
                print("Timeout occurred while waiting for response.")
                return
            '''
            
    
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
                