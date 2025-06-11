import cv2
import numpy as np
import requests
import math
from typing import Tuple, Dict, List
import logging


class MAP:
    """OpenStreetMap renderer with multi-drone overlay & altitude-based detection zone circles

    Added: forward detection-zone circles based on drone altitude and camera FoV (RoboMaster TT) and overlap highlighting
    Logs each circle addition and draws them semi-transparent, with overlapping regions emphasized.
    Supports auto-centering to fit all given points at fixed zoom.
    """

    def __init__(self, *, zoom: int = 18):
        self.zoom = zoom
        self.tile_size = 256
        self.display_size = 256
        self.buffer_size = 3 * self.tile_size

        # networking
        self.tile_server = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "DroneGCS/1.0"})

        # tile buffer and images
        self.tile_buffer: Dict[Tuple[int, int], np.ndarray] = {}
        self.buffer_image = np.full((self.buffer_size, self.buffer_size, 3), 200, dtype=np.uint8)
        self.map_img = np.zeros((360, 360, 3), np.uint8)

        # view state
        self.current_tile: Tuple[int, int] = (0, 0)
        self.global_pixel_x = 0
        self.global_pixel_y = 0

        # for detection circles accumulation
        self.prev_inputs = None
        self.circles: List[Tuple[int, int, int, Tuple[int, int, int]]] = []

        # logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            fmt = logging.Formatter('%(asctime)s - %(message)s')
            handler.setFormatter(fmt)
            self.logger.addHandler(handler)

    # coordinate conversion helpers
    @staticmethod
    def _deg_to_tile(lat: float, lon: float, zoom: int) -> Tuple[float, float]:
        lat_rad = math.radians(lat)
        n = 2.0 ** zoom
        x_tile = (lon + 180.0) / 360.0 * n
        y_tile = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
        return x_tile, y_tile

    @staticmethod
    def _tile_to_deg(x_tile: float, y_tile: float, zoom: int) -> Tuple[float, float]:
        n = 2.0 ** zoom
        lon = x_tile / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y_tile / n)))
        return math.degrees(lat_rad), lon

    def _latlon_to_global_pixels(self, lat: float, lon: float) -> Tuple[float, float]:
        n = 2 ** self.zoom * self.tile_size
        x = (lon + 180) / 360 * n
        y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
        return x, y

    def _latlon_to_local(self, lat: float, lon: float) -> Tuple[int, int]:
        n = 2 ** self.zoom
        gx = int((lon + 180) / 360 * n * self.tile_size)
        gy = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n * self.tile_size)
        dx = gx - self.global_pixel_x + self.display_size // 2
        dy = gy - self.global_pixel_y + self.display_size // 2
        return dx, dy

    def _meters_to_pixels(self, lat: float, meters: float) -> float:
        R = 6378137.0
        lat_rad = math.radians(lat)
        resolution = (math.cos(lat_rad) * 2 * math.pi * R) / (self.tile_size * 2 ** self.zoom)
        return meters / resolution

    # tile management
    def _load_tile(self, x: int, y: int) -> np.ndarray:
        try:
            url = self.tile_server.format(z=self.zoom, x=x, y=y)
            r = self.session.get(url, timeout=3)
            if r.status_code == 200:
                data = np.frombuffer(r.content, dtype=np.uint8)
                return cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception:
            pass
        return np.full((self.tile_size, self.tile_size, 3), 200, dtype=np.uint8)

    def _ensure_buffer(self, tile_x: float, tile_y: float):
        self.buffer_image.fill(200)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                tx, ty = int(tile_x) + dx, int(tile_y) + dy
                if (tx, ty) not in self.tile_buffer:
                    self.tile_buffer[(tx, ty)] = self._load_tile(tx, ty)
                tile_img = self.tile_buffer[(tx, ty)]
                y0, x0 = (dy + 1) * self.tile_size, (dx + 1) * self.tile_size
                self.buffer_image[y0:y0+self.tile_size, x0:x0+self.tile_size] = tile_img
        for key in list(self.tile_buffer.keys()):
            if abs(key[0] - int(tile_x)) > 1 or abs(key[1] - int(tile_y)) > 1:
                del self.tile_buffer[key]

    def _update_center(self, lat: float, lon: float):
        tx, ty = self._deg_to_tile(lat, lon, self.zoom)
        self.global_pixel_x = int((lon + 180) / 360 * 2**self.zoom * self.tile_size)
        self.global_pixel_y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * 2**self.zoom * self.tile_size)
        if (int(tx), int(ty)) != self.current_tile:
            self.current_tile = (int(tx), int(ty))
            self._ensure_buffer(tx, ty)

    def _render_base(self) -> np.ndarray:
        lx = (self.global_pixel_x % self.tile_size) + self.tile_size
        ly = (self.global_pixel_y % self.tile_size) + self.tile_size
        xs = lx - self.display_size//2
        ys = ly - self.display_size//2
        return self.buffer_image[ys:ys+self.display_size, xs:xs+self.display_size].copy()

    @staticmethod
    def _draw_iso_triangle(img: np.ndarray, pos: Tuple[int, int], yaw_deg: float, size: int, color: Tuple[int,int,int]):
        tip = np.array(pos, dtype=int)
        rad = math.radians(yaw_deg)
        base_center = tip - np.array([size*math.cos(rad), -size*math.sin(rad)], dtype=int)
        half_w = size * 0.6
        perp = np.array([math.sin(rad), math.cos(rad)])
        left = base_center + perp * half_w
        right = base_center - perp * half_w
        pts = np.array([tip, left.astype(int), right.astype(int)], dtype=np.int32)
        cv2.fillConvexPoly(img, pts, color)

    def update_map(self, center: List[float], extras: List, poi: List[float]) -> np.ndarray:
        """
        center: [lat, lon, yaw, alt]
        extras: ["Name", lat, lon, yaw, alt, ...]
        poi: [lat, lon]
        """
        curr_inputs = (tuple(center), tuple(extras), tuple(poi))
        if curr_inputs != self.prev_inputs:
            self.prev_inputs = curr_inputs
            FOV_DEG = 82.6
            half_fov = math.radians(FOV_DEG / 2)

            # center drone detection zone
            lat_c, lon_c, yaw_c, alt_c = center
            ex_c = ey_c = self.display_size // 2
            rad_c = math.radians(yaw_c)
            off_c_px = self._meters_to_pixels(lat_c, alt_c)
            detect_m = alt_c * math.tan(half_fov)
            r_c_px = int(self._meters_to_pixels(lat_c, detect_m))
            cx_c = int(ex_c + off_c_px * math.cos(rad_c))
            cy_c = int(ey_c - off_c_px * math.sin(rad_c))
            self.circles.append((cx_c, cy_c, r_c_px, (0, 0, 255)))
            self.logger.info(f"Added center-circle at ({cx_c},{cy_c}) r={r_c_px}px")

            # extras drones detection zones
            for i in range(0, len(extras), 5):
                name, lat_e, lon_e, yaw_e, alt_e = extras[i:i+5]
                ex_e, ey_e = self._latlon_to_local(lat_e, lon_e)
                rad_e = math.radians(yaw_e)
                off_e_px = self._meters_to_pixels(lat_e, alt_e)
                detect_e_m = alt_e * math.tan(half_fov)
                r_e_px = int(self._meters_to_pixels(lat_e, detect_e_m))
                cx_e = int(ex_e + off_e_px * math.cos(rad_e))
                cy_e = int(ey_e - off_e_px * math.sin(rad_e))
                self.circles.append((cx_e, cy_e, r_e_px, (255, 0, 0)))
                self.logger.info(f"Added extra-circle at ({cx_e},{cy_e}) r={r_e_px}px")

        # render base map
        lat_c, lon_c, _, _ = center
        self._update_center(lat_c, lon_c)
        frame = self._render_base()

        # draw detection circles on overlay
        overlay = frame.copy()
        for x, y, r, col in self.circles:
            cv2.circle(overlay, (x, y), r, col, -1)

        # detect overlapping regions between any two circles
        overlap_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        for i in range(len(self.circles)):
            x1, y1, r1, _ = self.circles[i]
            mask1 = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.circle(mask1, (x1, y1), r1, 255, -1)
            for j in range(i+1, len(self.circles)):
                x2, y2, r2, _ = self.circles[j]
                mask2 = np.zeros(frame.shape[:2], dtype=np.uint8)
                cv2.circle(mask2, (x2, y2), r2, 255, -1)
                inter = cv2.bitwise_and(mask1, mask2)
                overlap_mask = cv2.bitwise_or(overlap_mask, inter)

        # highlight overlap on overlay
        highlight_color = (0, 255, 255)  # yellow for overlap
        overlay[overlap_mask == 255] = highlight_color

        # blend overlay onto frame
        cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)

        # draw drones (triangles) and labels
        ex_c = ey_c = self.display_size // 2
        _, _, yaw_c, _ = center
        self._draw_iso_triangle(frame, (ex_c, ey_c), yaw_c, 6, (0, 0, 255))
        for name, lat_e, lon_e, yaw_e, _ in zip(extras[0::5], extras[1::5], extras[2::5], extras[3::5], extras[4::5]):
            pos = self._latlon_to_local(lat_e, lon_e)
            self._draw_iso_triangle(frame, pos, yaw_e, 5, (255, 0, 0))
            cv2.putText(frame, name, (pos[0]+6, pos[1]-6), cv2.FONT_HERSHEY_PLAIN, 0.7, (255, 0, 0), 1)

        # draw POI
        px, py = self._latlon_to_local(poi[0], poi[1])
        cv2.circle(frame, (px, py), 3, (0, 255, 0), -1)

        # scale up for display
        self.map_img = cv2.resize(frame, (360, 360), interpolation=cv2.INTER_LINEAR)
        return self.map_img

    def get_map(self) -> np.ndarray:
        return self.map_img


def main():
    m = MAP(zoom=17)
    center = [37.5665, 126.9780, 90, 10.0]
    extras = [
        "Alpha", 37.56652, 126.97802, 45, 12.0,
        "Bravo", 37.56648, 126.97798, 270, 8.0
    ]
    poi = [37.5658, 126.9753]

    frame = m.update_map(center, extras, poi)
    cv2.imshow("Map test", frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    speed, fps, R = 3.0, 30.0, 6378137.0
    dt = 1.0 / fps
    for tick in range(1000):
        for i in range(0, len(extras), 5):
            lat = extras[i+1]
            lon = extras[i+2]
            yaw = extras[i+3]
            dx = speed * dt * math.cos(math.radians(yaw))
            dy = speed * dt * math.sin(math.radians(yaw))
            extras[i+1] += (dy / R) * (180.0 / math.pi)
            extras[i+2] += (dx / (R * math.cos(math.radians(lat)))) * (180.0 / math.pi)

        center[2] += 1
        frame = m.update_map(center, extras, poi)
        cv2.imshow("Map test", frame)
        if cv2.waitKey(int(1000/fps)) == 27:
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
