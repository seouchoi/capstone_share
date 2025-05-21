from Custum_Tello import Tello
from Get_Video import VideoReceiver
from Mission_Command import Commander
import multiprocessing
import time
from Gcs_connector import GcsConnector
from typing import Any, Dict, List, Optional, Union
import asyncio
#tello1 = 111
#tello2 = 110

# def tello_setting(tello_address, control_port, tello_to_main_pipe): #각각의 프로세스에서 먼저 세팅되는 tello_setting함수
#     tello = Tello(tello_address, control_port, tello_to_main_pipe) #객체 선언
#     if not tello.connect(): #tello 연결 시도
#         print(f"[ERROR] 드론 연결 실패: {tello_address}")
#         return

#     #commander로부터 명령을 받아오는 함수(Custum_Tello파일 참고)
#     tello.tello_control()

#     #commander 객체에서 파이프로 받아온 함수를 처리하는 부분(변경 가능성 매우 높음)
#     # while True:
#     #     if tello_to_main_pipe.poll():
#     #         func_name, args, kwargs = tello_to_main_pipe.recv()
#     #         try:
#     #             func = getattr(tello, func_name)
#     #             func(*args, **kwargs)
#     #             print(f"[{tello_address}] {func_name} 실행됨")
#     #         except Exception as e:
#     #             print(f"[{tello_address}] {func_name} 실행 오류: {e}")
          
#     # 상태 유지용 heartbeat
#     # try:
#     #     while True:
#     #         try:
#     #             tello.send_command("battery?")  # ping 역할
#     #             status_queue.put(True)
#     #         except:
#     #             status_queue.put(False)
#     #         time.sleep(2)
#     # except KeyboardInterrupt:
#     #     tello.send_command("land")
#     #     print(f"[STOP] 드론 제어 종료 → {tello_address}")

# def run_video_receiver(tello_info, video_to_main_pipe): #비디오 리시버 함수수
#     tello_ips = [] #tello의 고유 주소를 저장할 리스트
#     for i, (name, (ip, port)) in enumerate(tello_info.items()): #tello_info = {"tello1": ["192.168.10.1", 9000], "tello2": ["192.168.10.2", 9001]} 
#         tello_ips.append(ip)
#     vr = VideoReceiver(tello_ips, video_to_main_pipe) #tello들의 주소와, 그 전용 파이프를 비디오 리시버에 넣음
#     vr.vid_main() #비디오 리시버 실행

# async def main():
#     #사전 초기 설정
#     tello_info = {"tello1": ["192.168.10.1", 9000], "tello2": ["192.168.10.2", 9001]} #각 tello의 별명과 ip, 그에 연결할 port번호 정의 
#     main_to_tello_pipes = {} #메인 -> 텔로로 향하는 파이프 딕셔너리(메인 -> 텔로1, 메인 -> 텔로2) 
#     #1. GCS선언 및 입력 부분

#     #2. 드론 제어 프로세스 2개 실행
#     control_procs = []
#     for i, (name, (ip, port)) in enumerate(tello_info.items()):
#         globals()[f"main_to_tello_pipe_{ip}"], globals()[f"tello_to_main_pipe_{ip}"] = multiprocessing.Pipe()   #메인과 텔로 프로세스를 이어줄 파이프를 만듦.
#         main_to_tello_pipes[f"tello{i}"] = globals()[f"main_to_tello_pipe_{ip}"] #{"tello1" : main_to_tello_pipe_{ip}}
#         p = multiprocessing.Process(target = tello_setting, args=(ip, port, globals()[f"tello_to_main_pipe_{ip}"])) #각각의 드론에 대해서 프로세스 실행.(만들어진 파이프도 줆.)
#         p.start() #텔로 프로세스 실행.
#         control_procs.append(p) #컨트롤 프로세스에 해당 프로세스를 추가함
#         print(f"[INFO] 드론 제어 프로세스 실행됨 → {name}")

#     #3. 비디오 프로세스 실행
#     main_to_video_pipe, video_to_main_pipe = multiprocessing.Pipe() #메인 프로세스와 비디오 프로세스를 연결시키는 파이프 정의
#     video_proc = multiprocessing.Process(target=run_video_receiver, args=(tello_info, video_to_main_pipe)) #비디오 프로세스 정의(파이프도 입력)
#     video_proc.start() #비디오 프로세스 실행
#     print("[INFO] VideoReceiver 프로세스 실행됨")
    
#     #4. Map 좌표추정 프로세스 실행
    
#     #5. Commander에서 상태 모니터링 및 미션 제어(스레드로 실행할 예정정)
#     commander = Commander(tello_info, main_to_tello_pipes,) #Commander객체를 선언해서 실행시킴(해당 객체는 메인 프로세스에서 스레드로 실행될 예정.)
#     commander.mission_start()

#     #6. 메인 드론 동작 프로세스
    
    
    


# #if __name__ == "__main__":
# #    multiprocessing.set_start_method("spawn") #윈도우 호환 멀티프로세싱 실행.
# #    main()


def run_video_receiver(tello_ips, video_to_main_pipe) -> None:
    vr = VideoReceiver(tello_ips, video_to_main_pipe)
    vr.vid_main()


def run_tello_process(name : str, tello_address : str, control_port : int, tello_to_main_pipe : Any, drone_locaion_Array : Any, drone_location_lock : Any) -> None:
    tello = Tello(name, tello_address, control_port, tello_to_main_pipe,drone_locaion_Array, drone_location_lock) #객체 선언
    if not tello.connect(): #tello 연결 시도
        print(f"[ERROR] 드론 연결 실패: {tello_address}")
        return
    tello.tello_control()


class Main:
    def __init__(self) -> None:
        self.tello_info : Dict = {"tello0": ["192.168.10.1", 9000]}#,
                                  #"tello1": ["192.168.10.2", 9001]}
        self.tello_ips : List = []
        self.main_to_tello_pipes : Dict = {}
        self.control_procs : List = []
        self.main_to_video_pipe, self.video_to_main_pipe = multiprocessing.Pipe()
        self.main_to_gcs_pipe, self.gcs_to_main_pipe = multiprocessing.Pipe()
        self.gcs_connecter = GcsConnector(self.gcs_to_main_pipe)
        self.drone_locaion_Array : Any = multiprocessing.Array("d", 3)
        self.drone_location_lock : Any = multiprocessing.Lock()
        with self.drone_location_lock:
            self.drone_locaion_Array[0] = 0.0
            self.drone_locaion_Array[1] = 0.0
            self.drone_locaion_Array[2] = 0.0
        print("[INFO] GCS 연결됨")
        print("[INFO] 드론 제어 프로세스 시작됨")
        
        
    async def main(self) -> None:
        self.gcs_connecter.start()
        for i, (name, (ip, port)) in enumerate(self.tello_info.items()):
            self.tello_ips.append(ip)
            globals()[f"main_to_tello_pipe_{ip}"], globals()[f"tello_to_main_pipe_{ip}"] = multiprocessing.Pipe()   #메인과 텔로 프로세스를 이어줄 파이프를 만듦.
            self.main_to_tello_pipes[f"tello{i}"] = globals()[f"main_to_tello_pipe_{ip}"] #{"tello1" : main_to_tello_pipe_{ip}}
            p = multiprocessing.Process(target = run_tello_process, args=(name,
                                                                          ip, 
                                                                          port, 
                                                                          globals()[f"tello_to_main_pipe_{ip}"],
                                                                          self.drone_locaion_Array,
                                                                          self.drone_location_lock,
                                                                          )) #각각의 드론에 대해서 프로세스 실행.(만들어진 파이프, 드론 위치 배열, 락도 줌.)
            p.start() #텔로 프로세스 실행.
            self.control_procs.append(p) #컨트롤 프로세스에 해당 프로세스를 추가함
            print(f"[INFO] 드론 제어 프로세스 실행됨 → {name}")
        video_proc = multiprocessing.Process(target=run_video_receiver, args=(self.tello_ips, self.video_to_main_pipe)) 
        video_proc.start()
        print("[INFO] VideoReceiver 프로세스 실행됨")
        commander = Commander(self.tello_info, self.main_to_tello_pipes) #Commander객체를 선언해서 실행시킴(해당 객체는 메인 프로세스에서 스레드로 실행될 예정.)
        commander.start()
        print("[INFO] Commander 프로세스 실행됨")
        #임시
        while True:
            with self.drone_location_lock:
                self.drone_locaion_Array[0] += 3.5
            time.sleep(0.1)
                
            
        # 종료 처리
        try:
            for p in control_procs + [video_proc]:
                p.join()
        except KeyboardInterrupt:
            print("[TEST END] 종료 요청")
            for p in control_procs + [video_proc]:
                p.terminate()
        
if __name__ == "__main__":
    multiprocessing.set_start_method("spawn") #윈도우 호환 멀티프로세싱 실행.
    main = Main()
    asyncio.run(main.main()) 