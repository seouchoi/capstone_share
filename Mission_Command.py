class Commander:
    def __init__(self,tello_info: dict, main_to_tello_pipes: dict, gcs_pipe):
        self.tello_info = tello_info #tello 정보가 들어가있는 딕셔너리
        self.main_to_tello_pipes = main_to_tello_pipes #main쪽에 연결돼어있는 파이프(tello와 연결결)
        self.gcs_pipe = gcs_pipe #(사실 뭔지 모름. 확실해지면 주석 처리)
        self.death_drone = [] #죽은 드론을 저장하는 리스트
        
    def is_alive(self) -> str:
        for name, pipe in self.main_to_tello_pipes.items(): #파이프 딕셔너리 순회
            if name not in self.death_drone: #death_drone 목록에 이름이 없다면 시작
                pipe.send(("get_battery", (), {})) #heartbeat 확인용 메세지
                if not pipe.poll(0.1): #0.1초동안 답이 오지 않으면 death_drone에 해당 드론을 추가시킴
                    self.death_drone.append(name)
                    return name  # 해당 드론을 반환 (즉, 죽은 것으로 간주)
                else:
                    _ = pipe.recv() #응답 큐를 비워주기위한 것
        return None  # 모두 살아있으면 None 반환

        
    #아래와 같은 형식으로 명령을 주면됨.(Action class에서 제대로 만들어져야함.)
    def situation_1(self) -> None:
        #쌈뽕하게 작성한 부분(효율은 좋지만 가독성 구림)
        self.pipes["tello1"].send(("takeoff", (), {})) 
        
        #굉장히 쉬움. if문을 이용해서 사용 가능능
        # self.pipes["tello2"].send("takeoff")
        pass
        
    def situation_2(self, death) -> None:
        if death == "tello1":
            #tello2에 대한 명령
            pass
        else:
            #tello1에 대한 명령령
            pass
        pass
    
    #처음은 드론 두 대만 사용할 것이므로 드론이 2개 일 때, 1개 일 때만 상황이 주어짐
    # def situation_3(self):
    #     pass
        
    #드론이 모두 살아있으면 sit_1, 하나만 살아있으면 sit_2
    #여기서 situation을 반복문을 계속 돌려서 drone_count가 줄어들면 그게 맞게 행동을 바꾸도록 해야함.
    #함수를 비동기로 만들어서 하던지, 또는 메인 프로세스에서 스레드를 하나 만들어서 commander용으로 할건지 결정해야함.
    async def mission_start(self) -> None:
        while True:
            death = self.is_alive() #드론이 먼저 둘 다 살아있는지 확인
            if death is None: #드론이 모두 살아있을 때
                self.situation_1()
            else: #드론이 하나라도 죽었을 때때
                self.situation_2(death)
                