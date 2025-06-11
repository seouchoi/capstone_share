# map_visualization.py
import cv2
import threading
import numpy as np
import requests
import time
import Drone_state
import math
from typing import Tuple, Dict, List

class MAP:
    def __init__(
        self,
        main_drone: Drone_state.DRONE_STATE,
        sub_drones: List[Drone_state.DRONE_STATE],
        fps: int = 30,
        zoom: int = 15,
    ) -> None:
        # 드론 상태
        self.drone_states: Dict[str, Drone_state.DRONE_STATE] = {'main': main_drone}
        for i, sd in enumerate(sub_drones, 1):
            self.drone_states[f'sub{i}'] = sd

        # 색상
        self.colors: Dict[str, Tuple[int, int, int]] = {
            'main': (0, 0, 255),
            'sub1': (0, 255, 0),
            'sub2': (255, 0, 0),
        }
        self.detect_history: List[Tuple[str, float, float, float]] = []

        # 맵 설정
        self.fps = fps
        self.zoom = zoom
        self.tile_size = 256
        self.display_size = 256
        self.buffer_size = self.tile_size * 3
        self.tile_buffer: Dict[Tuple[int, int], np.ndarray] = {}
        self.current_tile: Tuple[int, int] = (0, 0)
        self.lock = threading.Lock()
        self.tile_url = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'DroneGCS/1.0'})

        # 이미지 버퍼
        self.buffer_img = np.ones((self.buffer_size, self.buffer_size, 3), np.uint8) * 255
        self.map_img = np.zeros((360, 360, 3), np.uint8)

        # 백그라운드 업데이트
        thread = threading.Thread(target=self.update_map, daemon=True)
        thread.start()

    def deg_to_tile(self, lat: float, lon: float, z: int) -> Tuple[float, float]:
        lat_rad = math.radians(lat)
        n = 2 ** z
        x = (lon + 180.0) / 360.0 * n
        y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
        return x, y

    def load_tile(self, tx: int, ty: int) -> np.ndarray:
        try:
            url = self.tile_url.format(z=self.zoom, x=tx, y=ty)
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                arr = np.frombuffer(resp.content, np.uint8)
                return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except:
            pass
        return np.ones((self.tile_size, self.tile_size, 3), np.uint8) * 200

    def update_buffer(self, cx_tile: float, cy_tile: float) -> None:
        with self.lock:
            self.buffer_img.fill(200)
            cx = int(cx_tile)
            cy = int(cy_tile)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    pos = (cx + dx, cy + dy)
                    if pos not in self.tile_buffer:
                        self.tile_buffer[pos] = self.load_tile(*pos)
                    y0 = (dy + 1) * self.tile_size
                    x0 = (dx + 1) * self.tile_size
                    self.buffer_img[y0:y0 + self.tile_size, x0:x0 + self.tile_size] = self.tile_buffer[pos]
            # 오래된 타일 삭제
            for pos in list(self.tile_buffer):
                if abs(pos[0] - cx) > 1 or abs(pos[1] - cy) > 1:
                    del self.tile_buffer[pos]

    def update_center(self, lat: float, lon: float) -> None:
        tx, ty = self.deg_to_tile(lat, lon, self.zoom)
        n = 2 ** self.zoom
        self.center_px = int((lon + 180.0) / 360.0 * n * self.tile_size)
        self.center_py = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n * self.tile_size)
        tile_key = (int(tx), int(ty))
        if tile_key != self.current_tile:
            self.current_tile = tile_key
            self.update_buffer(tx, ty)

    def meters_to_pixels(self, meters: float, lat: float) -> float:
        lat_rad = math.radians(lat)
        m_per_px = 156543.03392 * math.cos(lat_rad) / (2 ** self.zoom)
        return meters / m_per_px

    def draw_sector(self, img: np.ndarray, lat: float, lon: float, heading: float,
                    color: Tuple[int, int, int], alpha: float, line_thickness: int) -> None:
        # 좌표 변환
        n = 2 ** self.zoom
        px = int((lon + 180.0) / 360.0 * n * self.tile_size)
        py = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n * self.tile_size)
        cx = self.display_size // 2 + (px - self.center_px)
        cy = self.display_size // 2 + (py - self.center_py)

        # 거리
        fwd = self.meters_to_pixels(20, lat)
        side = self.meters_to_pixels(10, lat)
        rad = math.radians(heading)
        pts = np.array([
            [cx, cy],
            [cx + fwd * math.sin(rad), cy - fwd * math.cos(rad)],
            [cx + side * math.cos(rad), cy + side * math.sin(rad)],
            [cx - side * math.cos(rad), cy - side * math.sin(rad)]
        ], np.int32)

        # 채우기
        overlay = img.copy()
        cv2.fillPoly(overlay, [pts], color)
        cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
        # 테두리
        cv2.polylines(img, [pts], True, color, line_thickness, cv2.LINE_AA)

    def render_map(self) -> np.ndarray:
        # 배경 잘라내기
        tx = self.center_px % self.tile_size + self.tile_size
        ty = self.center_py % self.tile_size + self.tile_size
        x0 = tx - self.display_size // 2
        y0 = ty - self.display_size // 2
        base = self.buffer_img[y0:y0 + self.display_size, x0:x0 + self.display_size].copy()
        overlay = base.copy()

        # 과거 탐지 (연한)
        for key, lat, lon, hd in self.detect_history:
            self.draw_sector(overlay, lat, lon, hd, self.colors[key], alpha=0.2, line_thickness=1)

        # 현재 탐지 (진한)
        for key, ds in self.drone_states.items():
            lat, lon = ds.get_drone_location_streaming()
            hd = ds.get_drone_heading_streaming()
            self.detect_history.append((key, lat, lon, hd))
            self.draw_sector(overlay, lat, lon, hd, self.colors[key], alpha=0.8, line_thickness=4)

        # 합성 및 출력 크기
        result = cv2.addWeighted(overlay, 0.6, base, 0.4, 0)
        return cv2.resize(result, (360, 360), interpolation=cv2.INTER_LINEAR)

    def update_map(self) -> None:
        while True:
            try:
                lat, lon = self.drone_states['main'].get_drone_location_streaming()
                self.update_center(lat, lon)
                self.map_img = self.render_map()
            except Exception:
                cv2.putText(self.map_img, 'map load false', (100, 180),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
            time.sleep(1 / self.fps)

    def get_map(self) -> np.ndarray:
        return self.map_img

# example_flight.py
if __name__ == '__main__':
    import cv2
    import Drone_state
    import math
    from threading import Thread
    import time

    class CircleDrone(Drone_state.DRONE_STATE):
        def __init__(self, center: Tuple[float, float], radius: float, speed: float):
            self.cx, self.cy = center
            self.r = radius
            self.speed = speed
            self.t = 0.0
            self.lat, self.lon = self.cx + self.r, self.cy
            self.heading = 0.0
            Thread(target=self._move, daemon=True).start()

        def _move(self):
            while True:
                self.lat = self.cx + self.r * math.cos(self.t)
                self.lon = self.cy + self.r * math.sin(self.t)
                dlat = -self.r * math.sin(self.t)
                dlon = self.r * math.cos(self.t)
                self.heading = (90 - math.degrees(math.atan2(dlon, dlat))) % 360
                self.t += self.speed * 0.02
                time.sleep(0.1)

        def get_drone_location_streaming(self) -> Tuple[float, float]:
            return self.lat, self.lon

        def get_drone_heading_streaming(self) -> float:
            return self.heading

    # 드론 인스턴스 생성
    main = CircleDrone((37.0, 127.0), 0.0008, 1.0)
    sub1 = CircleDrone((37.002, 127.002), 0.0006, 1.2)
    sub2 = CircleDrone((36.998, 126.998), 0.0007, 0.8)

    drone_map = MAP(main, [sub1, sub2], fps=15, zoom=15)
    while True:
        frame = drone_map.get_map()
        cv2.imshow('Drone Map (Free Paths)', frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
    cv2.destroyAllWindows()
