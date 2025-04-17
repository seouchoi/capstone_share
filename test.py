from djitellopy import Tello
import time
import threading
# from Odometry.Inertial_Odometry import InertialOdometry

# 드론 초기화
tello = Tello()
position = {'X': 0, 'Y': 0, 'Z': 0}

# 드론 연결 및 이륙
tello.connect()
print(f"드론 배터리 상태: {tello.get_battery()}%")

# 전진 명령 함수
def move_forward():
    tello.move("forward", 50)
    print("전진 완료")

def move_back():
    tello.move("back", 50)
    print("후진 완료")

# IMU 데이터 수집 함수
def collect_imu_data():
    global position
    last_time = time.time()
    # iner = InertialOdometry()
    try:
        while True:
            # 시간 간격 계산
            current_time = time.time()
            state = tello.get_current_state()
            delta_t = current_time - last_time


            print(state)
            #print(state)
            # position = iner.get_odometry(state, delta_t)
            # # 위치 출력
            # print(f"Position: {position['position']}")
            # last_time = current_time
            # # IMU 데이터 수집 주기
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("IMU 데이터 수집 중지")

# 스레드 생성 및 실행
imu_thread = threading.Thread(target=collect_imu_data)
imu_thread.daemon = True  # 메인 스레드 종료 시 함께 종료
imu_thread.start()

tello.takeoff()

time.sleep(1)
# # 전진 명령 실행
move_forward()

time.sleep(2)

# move_back()

try:
    # 메인 스레드는 계속 실행
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("사용자 종료 요청. 드론을 착륙합니다.")
    tello.land()

finally:
    tello.end()
