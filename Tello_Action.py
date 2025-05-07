import time

class Action:
    def send_command(self, cmd: str, wait_time: float = 2.0) -> str:
        self.socket_tello.sendto(cmd.encode('utf-8'), self.tello_address) #tello에다가 직접 명령을 내려주는 부분
        time.sleep(wait_time) #명령 내리고 조금 기다림(바꾸면됨)
        return self.get_response() #응답 수신신

    def get_battery(self):
        return self.send_command("battery?")
    # ✅ 기본 비행
    def takeoff(self):
        return self.send_command("takeoff")  # 자동 이륙

    def land(self):
        return self.send_command("land")     # 자동 착륙

    def emergency(self):
        return self.send_command("emergency")  # 즉시 모터 정지

    def stop(self):
        return self.send_command("stop")       # 공중 정지 (호버링)

    # ✅ 이동 명령 (단위: cm, 범위: 20 ~ 500)
    def forward(self, x: int):
        return self.send_command(f"forward {x}")  # 전진: 20~500 cm

    def back(self, x: int):
        return self.send_command(f"back {x}")     # 후진: 20~500 cm

    def left(self, x: int):
        return self.send_command(f"left {x}")     # 좌측 이동: 20~500 cm

    def right(self, x: int):
        return self.send_command(f"right {x}")    # 우측 이동: 20~500 cm

    def up(self, x: int):
        return self.send_command(f"up {x}")       # 상승: 20~500 cm

    def down(self, x: int):
        return self.send_command(f"down {x}")     # 하강: 20~500 cm

    # ✅ 회전 명령 (단위: 도, 범위: 1 ~ 360)
    def cw(self, degree: int):
        return self.send_command(f"cw {degree}")   # 시계방향 회전: 1~360도

    def ccw(self, degree: int):
        return self.send_command(f"ccw {degree}")  # 반시계방향 회전: 1~360도

    # ✅ 플립 (방향: l/r/f/b)
    def flip(self, direction: str):
        '''
        direction:
            'l' = 왼쪽
            'r' = 오른쪽
            'f' = 앞쪽
            'b' = 뒤쪽
        '''
        return self.send_command(f"flip {direction}")

    # ✅ 속도 설정 (단위: cm/s, 범위: 10 ~ 100)
    def set_speed(self, x: int):
        return self.send_command(f"speed {x}")  # 비행 속도 설정: 10~100 cm/s

    # ✅ 좌표 기반 이동 (단위: cm, x/y/z 범위: -500 ~ 500, speed: 10 ~ 100)
    def go(self, x: int, y: int, z: int, speed: int):
        '''
        이동 좌표:
            x, y, z: -500 ~ 500 (단, x/y/z 모두 동시에 -20~20 범위에 들어가면 안 됨)
            speed: 10 ~ 100 cm/s
        '''
        return self.send_command(f"go {x} {y} {z} {speed}")

    # ✅ 곡선 이동 (curve) – arc radius 제한 있음
    def curve(self, x1: int, y1: int, z1: int, x2: int, y2: int, z2: int, speed: int):
        '''
        곡선 좌표:
            x1~x2, y1~y2, z1~z2: -500 ~ 500
            speed: 10 ~ 60 cm/s
            (주의: x/y/z 모두 동시에 -20~20 안에 있으면 안 됨)
            곡선 반지름은 0.5m ~ 10m 이내
        '''
        return self.send_command(f"curve {x1} {y1} {z1} {x2} {y2} {z2} {speed}")
    
    ##예시 코드(만약 앞으로 갔다가 2초 후에 뒤로 가는 동작을 한다고 가정했을 때)
    def move_forward_and_back(self):
        self.forward()
        time.sleep(2)
        self.back()

