from djitellopy import Tello
import time, math

# === 파라미터 ===
X_SPEED        = 35       # [cm/s]  ← “세계 X축” 목표 속도
INTERVAL       = 0.02     # 50 Hz
YAW_PEAK       = 60       # rc yaw 피크값 (≈ 60 deg/s)
TURN_TIME      = 1.3      # s
HOLD_TIME_1    = 3.0      # s
HOLD_TIME_2    = 6.0
STRAIGHT_TIME  = 0.7      # s
CYCLES         = 2
ALTITUDE       = 40       # cm
FB_MAX         = 100      # rc 명령 상한

def gradual_zigzag(tello: Tello, cycles=CYCLES):
    tello.connect()
    tello.takeoff(); time.sleep(2)
    tello.move_up(ALTITUDE); time.sleep(2)

    print("[INFO] 🛫  keep X-axis 35 cm/s 시작")

    #y축 0을 기준으로 +- 움직이게 만듦.
    segments = [
        (-YAW_PEAK, TURN_TIME), #왼쪽 or 오른쪽으로 2.5초동안 진행
        (0, HOLD_TIME_1),
        
        ( YAW_PEAK, TURN_TIME), #기수를 반대로 돌리고 아주 잠깐 직진(드리프트 고려)
        (0, STRAIGHT_TIME),
        
        ( YAW_PEAK, TURN_TIME), #한번 더 기수를 돌려서 5초동안 진행
        (0, HOLD_TIME_2),
        
        (-YAW_PEAK, TURN_TIME), #기수를 반대로 돌리고 잠깐 직진함(드리프트 고려)
        (0, STRAIGHT_TIME),
        
        (-YAW_PEAK, TURN_TIME), #한번 더 기수를 돌리고 2.5초동안 진행
        (0, HOLD_TIME_1)
    ]

    yaw_deg = 0.0   # 추정 기수(세계 기준) 초기값

    for _ in range(cycles):
        for target_yaw, seg_t in segments:
            steps = int(seg_t / INTERVAL)

            if target_yaw != 0:                 # --- TURN (sin 램프) ---
                sign  = 1 if target_yaw > 0 else -1
                vmax  = abs(target_yaw)
                for i in range(steps):
                    phase     = i / (steps - 1)
                    yaw_rc    = sign * vmax * math.sin(math.pi * phase)   # deg/s
                    yaw_deg  += yaw_rc * INTERVAL                        # 적분
                    yaw_rad   = math.radians(yaw_deg)

                    # fb = X_SPEED / cosθ  (클램프)
                    fb_cmd = int(min(FB_MAX,  X_SPEED / max(1e-5, abs(math.cos(yaw_rad)))))
                    tello.send_rc_control(0, fb_cmd, 0, int(yaw_rc))
                    time.sleep(INTERVAL)

            else:                                 # --- 직진/유지 ---
                for _ in range(steps):
                    yaw_rad  = math.radians(yaw_deg)
                    fb_cmd = int(min(FB_MAX,  X_SPEED / max(1e-5, abs(math.cos(yaw_rad)))))
                    tello.send_rc_control(0, fb_cmd, 0, 0)
                    time.sleep(INTERVAL)

    tello.send_rc_control(0, 0, 0, 0)
    tello.land()
    print("[INFO] 🏁  flight done")

# === 실행 ===
if __name__ == "__main__":
    gradual_zigzag(Tello())
