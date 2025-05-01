from Custum_Tello import Tello
from Get_Video import VideoReceiver
from Mission_Command import Commander
import multiprocessing
import time

def tello_setting(tello_address, control_port, tello_to_main_pipe):
    tello = Tello(tello_address, control_port, tello_to_main_pipe)
    if not tello.connect():
        print(f"[ERROR] 드론 연결 실패: {tello_address}")
        return

    print(f"[INFO] 연결 성공 → {tello_address}")
    tello.socket_tello.sendto("command".encode("utf-8"), tello.tello_address)
    print(f"{tello_address}드론 command 전송 성공")
    tello.socket_tello.sendto("streamon".encode("utf-8"), tello.tello_address)
    print(f"{tello_address}드론 streamon 전송 성공")
    
    # 상태 유지용 heartbeat
    # try:
    #     while True:
    #         try:
    #             tello.send_command("battery?")  # ping 역할
    #             status_queue.put(True)
    #         except:
    #             status_queue.put(False)
    #         time.sleep(2)
    # except KeyboardInterrupt:
    #     tello.send_command("land")
    #     print(f"[STOP] 드론 제어 종료 → {tello_address}")

def run_video_receiver(tello_info, video_to_main_pipe):
    tello_ips = []
    for i, (name, (ip, port)) in enumerate(tello_info.items()):
        tello_ips.append(ip)
    vr = VideoReceiver(tello_ips, video_to_main_pipe)
    vr.vid_main()

async def main():
    #사전 초기 설정
    tello_info = {"tello1": ["192.168.10.1", 9000], "tello2": ["192.168.10.2", 9001]}

    #1. GCS선언 및 입력 부분

    #2. 드론 제어 프로세스 2개 실행
    control_procs = []
    for i, (name, (ip, port)) in enumerate(tello_info.items()):
        globals()[f"main_to_tello_pipe_{i}"], globals()[f"tello_to_main_pipe_{i}"] = multiprocessing.Pipe()     
        p = multiprocessing.Process(target = tello_setting, args=(name, ip, port, globals()[f"tello_to_main_pipe_{i}"]))
        p.start()
        control_procs.append(p)
        print(f"[INFO] 드론 제어 프로세스 실행됨 → {name}")

    #3. 비디오 프로세스 실행
    main_to_video_pipe, video_to_main_pipe = multiprocessing.Pipe()
    video_proc = multiprocessing.Process(target=run_video_receiver, args=(tello_info, video_to_main_pipe))
    video_proc.start()
    print("[INFO] VideoReceiver 프로세스 실행됨")
    
    #4. Map 프로세스 실행
    
    #5. Commander에서 상태 모니터링 및 미션 제어
    commander = Commander(tello_ips, status_queues)
    commander.mission_start()

    #6. 메인 드론 동작 프로세스스
    
    
    # 종료 처리
    try:
        for p in control_procs + [video_proc]:
            p.join()
    except KeyboardInterrupt:
        print("[TEST END] 종료 요청")
        for p in control_procs + [video_proc]:
            p.terminate()


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    main()
