import time
import math

class Action:
    def send_command(self, cmd: str, wait_time : float = 0) -> str:
        self.socket_tello.sendto(cmd.encode('utf-8'), self.tello_address) #tello에다가 직접 명령을 내려주는 부분
        return self.get_response(wait_time) #응답을 받음


    def command(self, wait_time: float = 3) -> str:
        self.empty_response()
        return self.send_command('command',wait_time) #응답을 받음
    
    
    def streamon(self, wait_time: float = 1) -> str:
        self.empty_response()
        return self.send_command('streamon',wait_time)


    def get_battery(self) -> None:
        self.empty_response()
        bat = self.send_command("battery?")
        self.tello_state['battery'] = bat #배터리 정보를 딕셔너리에 저장
        self.tello_to_main_pipe.send(bat) #배터리 정보를 메인으로 보내줌
        
        
    def update_state(self) -> None:
        self.empty_response()
        attitude = self.send_command("attitude?", wait_time = 0.1) #드론의 상태를 받아옴
        if attitude == 'error':
            return
        for part in attitude.split(';'):
            if part.startswith('yaw:'):
                self.tello_state['yaw'] = int(part.split(':')[1])
        height = self.send_command("height?", wait_time = 0.1) #드론의 높이를 받아옴
        if height == 'error':
            return
        if height.startswith('height:'):
            self.tello_state['height'] = int(height.split(':')[1])


    def takeoff(self):
        return self.send_command("takeoff")  # 자동 이륙


    def land(self):
        return self.send_command("land")     # 자동 착륙

    def go(self, x: int, y: int, z: int, speed: int):
        '''
        이동 좌표:
            x, y, z: -500 ~ 500 (단, x/y/z 모두 동시에 -20~20 범위에 들어가면 안 됨)
            speed: 10 ~ 100 cm/s
        '''
        return self.send_command(f"go {x} {y} {z} {speed}")
    
    def emergency(self):
        return self.send_command("emergency")  # 즉시 모터 정지


    def stop(self):
        return self.send_command("stop")       # 공중 정지 (호버링)


    def set_speed(self, x: int):
        return self.send_command(f"speed {x}")


    def cw(self, degree: int):
        return self.send_command(f"cw {degree}")   # 시계방향 회전: 1~360도
    
    
    def ccw(self, degree: int):
        return self.send_command(f"ccw {degree}")  # 반시계방향 회전: 1~360도
    

    def rc(self, lr: int, fb: int, ud: int, yaw: int) -> None:
        cmd = f"rc {lr} {fb} {ud} {yaw}"
        self.send_command(cmd, wait_time = -1)


    def double_sin_wave(self,
                        disp_amp: float = 80.0,   # y 변위 진폭(±cm)
                        fb_speed:  int   = 35,    # 전진 속도(cm/s)
                        interval:  float = 0.1,
                        side: str = "tello0"):
        """
        전진(x) + y 사인 변위(0 → ±A → 0) 한 사이클 실행.
        - side == "tello0" : +sin(…)  (첫 변위가 +방향)
        - side == "tello1" : -sin(…)  (첫 변위가 –방향)
        """
        # ── 부호 결정 ──────────────────────────────────────────────
        sign = 1 if side == "tello0" else -1   # 좌우 방향 반전

        # ── 1) 주기 자동 결정 (v_y ≤ 100) ─────────────────────────
        max_lr_speed_needed = 2 * math.pi * disp_amp       # |Aω|
        period = max(max_lr_speed_needed / 100.0, 3.0)     # 최소 3 s
        omega  = 2 * math.pi / period

        # ── 2) 제어 루프 ──────────────────────────────────────────
        start_t = time.time()
        est_yaw = 0.0

        while (t := time.time() - start_t) <= period:
            # (a) 좌우 속도 (±100 안으로)
            lr_speed = sign * disp_amp * omega * math.cos(omega * t)
            lr = int(max(-100, min(100, lr_speed)))

            # (b) 목표 헤딩
            tgt_yaw = math.degrees(math.atan2(lr, fb_speed))

            # (c) P 제어로 yaw rate 계산
            err = tgt_yaw - est_yaw
            if err > 180:  err -= 360
            if err < -180: err += 360
            d = int(max(-100, min(100, 1.8 * err)))

            # (d) rc 전송
            self.rc(lr, fb_speed, 0, d)

            # (e) yaw 추정
            est_yaw = (est_yaw + d * interval + 180) % 360 - 180
            time.sleep(interval)
        
        self.rc(0, 0, 0, 0)                     # 잠깐 정지
        time.sleep(0.2)

        if abs(est_yaw) > 2:                    # ±2° 이상이면 정렬
            rot_deg = int(round(abs(est_yaw)))
            if est_yaw > 0:
                # 기수가 CCW(+) 쪽으로 돌아가 있었다면 ↘︎ CW 로 복귀
                self.cw(rot_deg)
            else:
                # 기수가 CW(-) 쪽으로 돌아가 있었다면 ↖︎ CCW 로 복귀
                self.ccw(rot_deg)

            # 회전 시간: 각도/100 °·s⁻¹  + 여유
            time.sleep(rot_deg / 100 + 0.3)

        self.rc(0, 0, 0, 0)                     # 최종 호버
            
    def readjust_position(self,
                      side: str,            # 고장나지 않은 드론
                      diag_x: int = 100,    # x 성분(cm)
                      y_offset: int = 200,  # 메인 기준 초기 |y| 거리(cm)
                      shift_speed: int = 80,# go 속도 10~100 cm/s
                      settle: float = 0.5):
        """
        살아남은 드론(tello0 또는 tello1)을
        · 대각선 (x=diag_x , y=0) 위치로 go 이동
        · 헤딩은 그대로 유지
        """

        # ── 좌표계: +y = 오른쪽, -y = 왼쪽 ──────────────────────────
        # tello0 ⇒ 시작 y = -y_offset   (왼쪽)
        # tello1 ⇒ 시작 y = +y_offset   (오른쪽)
        start_y = -y_offset if side == "tello0" else y_offset

        # 센터로 가려면 Δy = -start_y
        go_x = diag_x
        go_y = -start_y

        # go 명령 (x, y, z, speed)
        self.go(go_x, go_y, 0, shift_speed)

        # 이동 시간 = √(x²+y²)/speed  + 여유
        move_time = math.hypot(go_x, go_y) / shift_speed + settle
        time.sleep(move_time)
        
        
    def solo_sin_wave(self,
                      disp_amp: float = 280.0,   # y 변위 진폭(±cm) = 280
                      fb_speed:  int   = 35,     # 전진 속도(cm/s) = 35
                      interval:  float = 0.1,
                      side: str = "tello0", 
                      k_p: float = 1.8):
        """
        서브 드론 단독 운영 시 넓은 영역(±280cm) 커버용 사인파 1사이클.
        - side  : "tello0" → +sin,  "tello1" → -sin
        - k_p   : 헤딩 추종 P 게인 (기본 1.8)
        """

        sign = 1 if side == "tello0" else -1

        # ── 주기 계산: v_y_peak ≤ 100 cm/s 조건 ──────────────────
        #   v_y_peak = A * ω  ≤ 100  →  ω = 2π/T  →  T = 2πA / 100
        period = (2 * math.pi * disp_amp) / 100.0        # ≈ 17.59 s
        omega  = 2 * math.pi / period

        start_t = time.time()
        est_yaw = 0.0

        while (t := time.time() - start_t) <= period:
            lr_speed = sign * disp_amp * omega * math.cos(omega * t)
            lr       = int(max(-100, min(100, lr_speed)))

            tgt_yaw = math.degrees(math.atan2(lr, fb_speed))
            err     = ((tgt_yaw - est_yaw + 180) % 360) - 180   # wrap‑to‑±180
            d       = int(max(-100, min(100, k_p * err)))

            self.rc(lr, fb_speed, 0, d)

            est_yaw = (est_yaw + d * interval + 180) % 360 - 180
            time.sleep(interval)

        # ── 호버 → 정면 복귀 ──────────────────────────────────────
        self.rc(0, 0, 0, 0)
        time.sleep(0.2)

        if abs(est_yaw) > 2:
            rot = int(round(abs(est_yaw)))
            (self.cw if est_yaw > 0 else self.ccw)(rot)
            time.sleep(rot / 100 + 0.3)

        self.rc(0, 0, 0, 0)






    # # ✅ 이동 명령 (단위: cm, 범위: 20 ~ 500)
    # def forward(self, x: int):
    #     return self.send_command(f"forward {x}")  # 전진: 20~500 cm

    # def back(self, x: int):
    #     return self.send_command(f"back {x}")     # 후진: 20~500 cm

    # def left(self, x: int):
    #     return self.send_command(f"left {x}")     # 좌측 이동: 20~500 cm

    # def right(self, x: int):
    #     return self.send_command(f"right {x}")    # 우측 이동: 20~500 cm

    # def up(self, x: int):
    #     return self.send_command(f"up {x}")       # 상승: 20~500 cm

    # def down(self, x: int):
    #     return self.send_command(f"down {x}")     # 하강: 20~500 cm

    # # ✅ 회전 명령 (단위: 도, 범위: 1 ~ 360)
    # def cw(self, degree: int):
    #     return self.send_command(f"cw {degree}")   # 시계방향 회전: 1~360도

    # def ccw(self, degree: int):
    #     return self.send_command(f"ccw {degree}")  # 반시계방향 회전: 1~360도

    # # ✅ 플립 (방향: l/r/f/b)
    # def flip(self, direction: str):
    #     '''
    #     direction:
    #         'l' = 왼쪽
    #         'r' = 오른쪽
    #         'f' = 앞쪽
    #         'b' = 뒤쪽
    #     '''
    #     return self.send_command(f"flip {direction}")



    # # ✅ 좌표 기반 이동 (단위: cm, x/y/z 범위: -500 ~ 500, speed: 10 ~ 100)
    # def go(self, x: int, y: int, z: int, speed: int):
    #     '''
    #     이동 좌표:
    #         x, y, z: -500 ~ 500 (단, x/y/z 모두 동시에 -20~20 범위에 들어가면 안 됨)
    #         speed: 10 ~ 100 cm/s
    #     '''
    #     return self.send_command(f"go {x} {y} {z} {speed}")

    # # ✅ 곡선 이동 (curve) – arc radius 제한 있음
    # def curve(self, x1: int, y1: int, z1: int, x2: int, y2: int, z2: int, speed: int):
    #     '''
    #     곡선 좌표:
    #         x1~x2, y1~y2, z1~z2: -500 ~ 500
    #         speed: 10 ~ 60 cm/s
    #         (주의: x/y/z 모두 동시에 -20~20 안에 있으면 안 됨)
    #         곡선 반지름은 0.5m ~ 10m 이내
    #     '''
    #     return self.send_command(f"curve {x1} {y1} {z1} {x2} {y2} {z2} {speed}")
    
    # ##예시 코드(만약 앞으로 갔다가 2초 후에 뒤로 가는 동작을 한다고 가정했을 때)
    # def move_forward_and_back(self):
    #     self.forward()
    #     time.sleep(2)
    #     self.back()

