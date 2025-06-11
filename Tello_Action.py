
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
        hold_time_1: float = 2.7,
        hold_time_2: float = 4.0,
        fb_max: int = 100,
        name: str = None,
        turn_deg = 45
    ):
        fb_speed = self.compute_drone_speed()
        print(f"[INFO] 🛫  double_sin_wave (cw/ccw + rc 직진): fb_speed = {fb_speed:.1f} cm/s")

        [pos_x, pos_y] = self.get_tello_location()
        yaw_deg = self.tello_state["yaw"]

        if name == "tello0":
            segments = [
                ("ccw", turn_deg),
                ("fwd", hold_time_1),
                ("cw", 2 * turn_deg),
                ("fwd", hold_time_2),
                ("ccw", 2 * turn_deg),
                ("fwd", hold_time_1),
                ("cw", turn_deg)
            ]
        elif name == "tello1":
            segments = [
                ("cw", turn_deg),
                ("fwd", hold_time_1),
                ("ccw", 2 * turn_deg),
                ("fwd", hold_time_2),
                ("cw", 2 * turn_deg),
                ("fwd", hold_time_1),
                ("ccw", turn_deg)
            ]
        else:
            raise ValueError(f"[ERROR] Unknown drone_id: {name}")

        for _ in range(cycles):
            ideal_deg = 0
            for action, value in segments:
                self.update_state()
                yaw_deg = self.tello_state["yaw"]
                if action in ("cw", "ccw"):
                    print(f"[TURN] {action} {value}°")
                    if action == "cw":
                        ideal_deg = (ideal_deg + value) % 360
                        diff = (ideal_deg - yaw_deg + 360) % 360
                        print(f"[TURN] cw: 목표={ideal_deg:.1f}, 현재={yaw_deg:.1f}, 보정={diff:.1f}")
                        self.cw(int(diff))
                        time.sleep(2)
                        yaw_deg += diff                  
                    else:
                        ideal_deg = (ideal_deg - value + 360) % 360
                        diff = (yaw_deg - ideal_deg + 360) % 360
                        print(f"[TURN] ccw: 목표={ideal_deg:.1f}, 현재={yaw_deg:.1f}, 보정={diff:.1f}")
                        self.ccw(int(diff))
                        time.sleep(2)
                        yaw_deg -= diff
                    self.update_tello_location(pos_x, pos_y, yaw_deg)

                elif action == "fwd":
                    print(f"[FWD] {value:.2f}s")
                    steps = int(value / interval)
                    for _ in range(steps):
                        yaw_rad = math.radians(yaw_deg)
                        fb_cmd = int(min(fb_max, fb_speed / max(1e-5, abs(math.cos(yaw_rad)))))
                        self.rc(0, fb_cmd, 0, 0)
                        time.sleep(interval)

                        distance = fb_cmd * interval
                        pos_x += distance * math.cos(yaw_rad)
                        pos_y += distance * math.sin(yaw_rad)
                        self.update_tello_location(pos_x, pos_y, yaw_deg)                  
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
        self.tello_to_main_pipe.send(('readjust_position','ok'))
        
    def solo_sin_wave(
            self,
            cycles: int = 1,
            interval: float = 0.02,
            hold_time_1: float = 4.7,
            hold_time_2: float = 8.0,
            fb_max: int = 100,
            name: str = None,
            turn_deg = 45
        ):
            fb_speed = self.compute_drone_speed()
            print(f"[INFO] 🛫  solo_sin_wave (cw/ccw + rc 직진): fb_speed = {fb_speed:.1f} cm/s")

            [pos_x, pos_y] = self.get_tello_location()
            yaw_deg = self.tello_state["yaw"]

            if name == "tello0":
                segments = [
                    ("ccw", turn_deg),
                    ("fwd", hold_time_1),
                    ("cw", 2 * turn_deg),
                    ("fwd", hold_time_2),
                    ("ccw", 2 * turn_deg),
                    ("fwd", hold_time_1),
                    ("cw", turn_deg)
                ]
            elif name == "tello1":
                segments = [
                    ("cw", turn_deg),
                    ("fwd", hold_time_1),
                    ("ccw", 2 * turn_deg),
                    ("fwd", hold_time_2),
                    ("cw", 2 * turn_deg),
                    ("fwd", hold_time_1),
                    ("ccw", turn_deg)
                ]
            else:
                raise ValueError(f"[ERROR] Unknown drone_id: {name}")

            for _ in range(cycles):
                ideal_deg = 0
                for action, value in segments:
                    self.update_state()
                    yaw_deg = self.tello_state["yaw"]
                    if action in ("cw", "ccw"):
                        print(f"[TURN] {action} {value}°")
                        if action == "cw":
                            ideal_deg = (ideal_deg + value) % 360
                            diff = (ideal_deg - yaw_deg + 360) % 360
                            print(f"[TURN] cw: 목표={ideal_deg:.1f}, 현재={yaw_deg:.1f}, 보정={diff:.1f}")
                            self.cw(int(diff))
                            time.sleep(2)
                            yaw_deg += diff                  
                        else:
                            ideal_deg = (ideal_deg - value + 360) % 360
                            diff = (yaw_deg - ideal_deg + 360) % 360
                            print(f"[TURN] ccw: 목표={ideal_deg:.1f}, 현재={yaw_deg:.1f}, 보정={diff:.1f}")
                            self.ccw(int(diff))
                            time.sleep(2)
                            yaw_deg -= diff
                        self.update_tello_location(pos_x, pos_y, yaw_deg)

                    elif action == "fwd":
                        print(f"[FWD] {value:.2f}s")
                        steps = int(value / interval)
                        for _ in range(steps):
                            yaw_rad = math.radians(yaw_deg)
                            fb_cmd = int(min(fb_max, fb_speed / max(1e-5, abs(math.cos(yaw_rad)))))
                            self.rc(0, fb_cmd, 0, 0)
                            time.sleep(interval)

                            distance = fb_cmd * interval
                            pos_x += distance * math.cos(yaw_rad)
                            pos_y += distance * math.sin(yaw_rad)
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

