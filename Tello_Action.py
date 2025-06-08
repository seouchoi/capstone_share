
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


    def get_battery(self, wait_time : float = 1) -> None:
        self.empty_response()
        bat = self.send_command("battery?",wait_time)
        self.tello_state['battery'] = bat #배터리 정보를 딕셔너리에 저장
        self.tello_to_main_pipe.send(('battery', bat)) #배터리 정보를 메인으로 보내줌
        
        
    def update_state(self, wait_time : float = 0.5) -> None:
        self.empty_response()
        attitude = self.send_command("attitude?", wait_time) #드론의 상태를 받아옴
        if attitude == 'error':
            return
        for part in attitude.split(';'):
            if part.startswith('yaw:'):
                self.tello_state['yaw'] = int(part.split(':')[1]) - self.tello_state['yaw_error']
        height = self.send_command("height?", wait_time) #드론의 높이를 받아옴
        if height == 'error':
            return
        if height.startswith('height:'):
            self.tello_state['height'] = int(height.split(':')[1])


    def takeoff(self, wait_time: float = 10) -> None:
        self.empty_response()
        res = self.send_command("takeoff",wait_time)  # 자동 이륙
        self.tello_to_main_pipe.send(('takeoff', res))


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

    
    def up(self, x: int = 500, wait_time: float = 10):
        self.empty_response()
        res = self.send_command(f"up {x}", wait_time)   
        self.tello_to_main_pipe.send(('takeoff', res))
        

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


    def double_sin_wave(
        self,
        cycles: int = 1,
        interval: float = 0.02,
        yaw_turn_speed: float = 60,
        turn_time: float = 1.0,
        hold_time_1: float = 2.0,
        hold_time_2: float = 4.0,
        straight_time: float = 0.7,
        fb_max: int = 100,
        name: str = None
    ):

        fb_speed = self.compute_drone_speed()            # cm/s
        print(f"[INFO] 🛫  smooth-yaw double_sin_wave: fb_speed = {fb_speed} cm/s")

        # (x, y) 시작 좌표. 없으면 원점으로 초기화
        [pos_x, pos_y] = self.get_tello_location()

        if name == "tello0": #tello0은 메인드론 기준 왼쪽에 배치되고, 왼쪽으로 먼저 움직임
            segments = [
                (-yaw_turn_speed, turn_time),   # 왼쪽부터 시작
                (0,                 hold_time_1),
                ( yaw_turn_speed,   turn_time),
                (0,                 straight_time),
                ( yaw_turn_speed,   turn_time),
                (0,                 hold_time_2),
                (-yaw_turn_speed,   turn_time),
                (0,                 straight_time),
                (-yaw_turn_speed,   turn_time),
                (0,                 hold_time_1),
                ( yaw_turn_speed,   turn_time)
            ]
        elif name == "tello1": #tello1은 메인드론 기준 오른쪽에 배치되고, 오른쪽으로 먼저 움직임
            segments = [
                ( yaw_turn_speed,   turn_time),  # 오른쪽부터 시작
                (0,                 hold_time_1),
                (-yaw_turn_speed,   turn_time),
                (0,                 straight_time),
                (-yaw_turn_speed,   turn_time),
                (0,                 hold_time_2),
                ( yaw_turn_speed,   turn_time),
                (0,                 straight_time),
                ( yaw_turn_speed,   turn_time),
                (0,                 hold_time_1),
                (-yaw_turn_speed,   turn_time)
            ]
        else:
            raise ValueError(f"[ERROR] Unknown drone_id: {name}")

        print("[INFO] 🛫  smooth-yaw double_sin_wave 시작")
        for _ in range(cycles):
            for target_yaw, seg_t in segments:
                steps = int(seg_t / interval)

                # 현재 기체 상태 한 번 읽어 둠
                self.update_state()
                yaw_deg = self.tello_state["yaw"]        # 현재 헤딩(도)

                if target_yaw != 0:                      # --- TURN 구간 ---
                    sign = 1 if target_yaw > 0 else -1
                    vmax = abs(target_yaw)               # 최대 yaw 속도(deg/s)

                    for i in range(steps):
                        # (1) sin 램프로 목표 yaw 속도
                        phase   = i / max(1, steps - 1)          # 0 → 1
                        yaw_rc  = sign * vmax * math.sin(math.pi * phase)  # deg/s

                        # (2) 적분해 yaw_deg 갱신
                        yaw_deg += yaw_rc * interval             # deg

                        # (3) fb_cmd 계산
                        yaw_rad = math.radians(yaw_deg)
                        fb_cmd  = int(min(fb_max,
                                        fb_speed / max(1e-5, abs(math.cos(yaw_rad)))))

                        # (4) RC 전송
                        self.rc(0, fb_cmd, 0, int(yaw_rc))
                        time.sleep(interval)

                        # (5) 위치 적분 (cm)
                        distance = fb_cmd * interval             # 이동 거리
                        pos_x   += distance * math.cos(yaw_rad)  # Δx
                        pos_y   += distance * math.sin(yaw_rad)  # Δy
                        self.update_tello_location(pos_x, pos_y, yaw_deg)

                else:                                   # --- 직선 전진 구간 ---
                    for _ in range(steps):
                        yaw_rad = math.radians(yaw_deg)
                        fb_cmd  = int(min(fb_max,
                                        fb_speed / max(1e-5, abs(math.cos(yaw_rad)))))
                        self.rc(0, fb_cmd, 0, 0)
                        time.sleep(interval)

                        distance = fb_cmd * interval
                        pos_x   += distance * math.cos(yaw_rad)
                        pos_y   += distance * math.sin(yaw_rad)
                        self.update_tello_location(pos_x, pos_y, yaw_deg)

        print(f"[INFO] ✅  flight finished — final location ≈ [{pos_x:.1f}, {pos_y:.1f}] cm")                  
        self.tello_to_main_pipe.send(('double_sin_wave','ok'))
               
               
    def readjust_position(
        self,
        name: str = None,                  # "tello0"(왼쪽) | "tello1"(오른쪽)
        angle_deg: float = 15,      # 가로(y)축과 이루는 각도
        y_fixed: int = 1000,        # y축 이동량(cm) = 10 m 고정
        shift_speed: int = 80,      # go 속도 10–100 cm/s
        diag_x: int = 100,          # 기존 보정용 파라미터(그대로 유지)
        y_offset: int = 200,
        settle: float = 0.5
    ):
        """
        살아남은 드론을 메인 쪽으로 재배치:
        1) 가로(y)축으로 ±10 m 이동하면서 angle_deg° 대각선 진입
        (y 고정 → x = y * tan(angle))
        2) 이후 기존 로직대로 (diag_x, -start_y) 위치로 go 이동
        """

        # ──────────────────────────────
        # 1️⃣  y축 ±1000 cm + 대각선 진입
        # ──────────────────────────────
        sign_y = 1 if name == "tello0" else -1      # tello0: +y(→) / tello1: –y(←)
        dy = sign_y * y_fixed                       # ±1000 cm
        dx = int(abs(dy) * math.tan(math.radians(angle_deg)))  # 항상 전진(+) 방향
        total_dist = math.hypot(dx, dy)

        print(f"[INFO] {name}: y={dy}cm, x={dx}cm (angle={angle_deg}°) 대각선 이동")
        self.go(dx, dy, 0, shift_speed)             # go(x=전진, y=좌우, z, speed)
        time.sleep(total_dist / shift_speed + settle)

        # ──────────────────────────────
        # 2️⃣  기존 대각선 (diag_x, -start_y) 보정
        # ──────────────────────────────
        start_y = -y_offset if name == "tello0" else y_offset
        go_x, go_y = diag_x, -start_y

        print(f"[INFO] {name}: 최종 위치 재조정 → x={go_x}, y={go_y}")
        self.go(go_x, go_y, 0, shift_speed)
        time.sleep(math.hypot(go_x, go_y) / shift_speed + settle)
        
        
    def solo_sin_wave(
        self,
        cycles: int = 1,
        interval: float = 0.02,
        yaw_turn_speed: float = 100,
        turn_time: float = 1.0,
        hold_time_1: float = 4.0,
        hold_time_2: float = 8.0,
        straight_time: float = 0.7,
        fb_max: int = 100,
        name: str = None
    ):

        fb_speed = self.compute_drone_speed()            # cm/s
        print(f"[INFO] 🛫  smooth-yaw solo_sin_wave: fb_speed = {fb_speed} cm/s")

        # (x, y) 시작 좌표. 없으면 원점으로 초기화
        [pos_x, pos_y] = self.get_tello_location()

        if name == "tello0": #tello0은 메인드론 기준 왼쪽에 배치되고, 왼쪽으로 먼저 움직임
            segments = [
                (-yaw_turn_speed, turn_time),   # 왼쪽부터 시작
                (0,                 hold_time_1),
                ( yaw_turn_speed,   turn_time),
                (0,                 straight_time),
                ( yaw_turn_speed,   turn_time),
                (0,                 hold_time_2),
                (-yaw_turn_speed,   turn_time),
                (0,                 straight_time),
                (-yaw_turn_speed,   turn_time),
                (0,                 hold_time_1),
                ( yaw_turn_speed,   turn_time)
            ]
        elif name == "tello1": #tello1은 메인드론 기준 오른쪽에 배치되고, 오른쪽으로 먼저 움직임
            segments = [
                ( yaw_turn_speed,   turn_time),  # 오른쪽부터 시작
                (0,                 hold_time_1),
                (-yaw_turn_speed,   turn_time),
                (0,                 straight_time),
                (-yaw_turn_speed,   turn_time),
                (0,                 hold_time_2),
                ( yaw_turn_speed,   turn_time),
                (0,                 straight_time),
                ( yaw_turn_speed,   turn_time),
                (0,                 hold_time_1),
                (-yaw_turn_speed,   turn_time)
            ]
        else:
            raise ValueError(f"[ERROR] Unknown drone_id: {name}")

        print("[INFO] 🛫  smooth-yaw double_sin_wave 시작")
        for _ in range(cycles):
            for target_yaw, seg_t in segments:
                steps = int(seg_t / interval)

                # 현재 기체 상태 한 번 읽어 둠
                self.update_state()
                yaw_deg = self.tello_state["yaw"]        # 현재 헤딩(도)

                if target_yaw != 0:                      # --- TURN 구간 ---
                    sign = 1 if target_yaw > 0 else -1
                    vmax = abs(target_yaw)               # 최대 yaw 속도(deg/s)

                    for i in range(steps):
                        # (1) sin 램프로 목표 yaw 속도
                        phase   = i / max(1, steps - 1)          # 0 → 1
                        yaw_rc  = sign * vmax * math.sin(math.pi * phase)  # deg/s

                        # (2) 적분해 yaw_deg 갱신
                        yaw_deg += yaw_rc * interval             # deg

                        # (3) fb_cmd 계산
                        yaw_rad = math.radians(yaw_deg)
                        fb_cmd  = int(min(fb_max,
                                        fb_speed / max(1e-5, abs(math.cos(yaw_rad)))))

                        # (4) RC 전송
                        self.rc(0, fb_cmd, 0, int(yaw_rc))
                        time.sleep(interval)

                        # (5) 위치 적분 (cm)
                        distance = fb_cmd * interval             # 이동 거리
                        pos_x   += distance * math.cos(yaw_rad)  # Δx
                        pos_y   += distance * math.sin(yaw_rad)  # Δy
                        self.update_tello_location(pos_x, pos_y, yaw_deg)

                else:                                   # --- 직선 전진 구간 ---
                    for _ in range(steps):
                        yaw_rad = math.radians(yaw_deg)
                        fb_cmd  = int(min(fb_max,
                                        fb_speed / max(1e-5, abs(math.cos(yaw_rad)))))
                        self.rc(0, fb_cmd, 0, 0)
                        time.sleep(interval)

                        distance = fb_cmd * interval
                        pos_x   += distance * math.cos(yaw_rad)
                        pos_y   += distance * math.sin(yaw_rad)
                        self.update_tello_location(pos_x, pos_y, yaw_deg)

        print(f"[INFO] ✅  flight finished — final location ≈ [{pos_x:.1f}, {pos_y:.1f}] cm")                  
        self.tello_to_main_pipe.send(('solo_sin_wave','ok'))
        






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

