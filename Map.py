import cv2
import numpy as np
import requests
import math
from typing import Tuple, Dict, List, Optional

class MAP:
    def __init__(self, *, zoom: int = 18):
        self.zoom = zoom
        self.tile_size = 256
        # 화면에 렌더링할 기본 display 크기 (픽셀)
        self.display_size = 256
        # 버퍼용: 3x3 타일
        self.buffer_size = 3 * self.tile_size

        # OpenStreetMap 타일 서버
        self.tile_server = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "DroneGCS/1.0"})

        # 타일 버퍼와 이미지
        self.tile_buffer: Dict[Tuple[int, int], np.ndarray] = {}
        self.buffer_image = np.full((self.buffer_size, self.buffer_size, 3), 200, dtype=np.uint8)
        # 반환할 map image
        self.map_img = np.zeros((360, 360, 3), np.uint8)

        # 뷰 상태: global pixel 기준
        self.current_tile: Tuple[int, int] = (0, 0)
        self.global_pixel_x = 0
        self.global_pixel_y = 0

        # POI (Optional)
        self.poi: Optional[List[float]] = None

        # 이전 입력 캐시
        self.prev_inputs = None

        # 드론별 마스크 관리
        # visited_mask: 드론별 과거 방문 이력
        self.visited_mask: Dict[str, np.ndarray] = {}
        # prev_frame_mask: 드론별 바로 직전 프레임 탐지 중이던 픽셀
        self.prev_frame_mask: Dict[str, np.ndarray] = {}

        # global 방문 카운트 마스크
        self.global_count_mask: Optional[np.ndarray] = None

    # ================= coordinate conversion helpers =================
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
        gx = int((lon + 180) / 360 * 2**self.zoom * self.tile_size)
        gy = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * 2**self.zoom * self.tile_size)
        dx = gx - self.global_pixel_x + self.display_size // 2
        dy = gy - self.global_pixel_y + self.display_size // 2
        return dx, dy

    def _meters_to_pixels(self, lat: float, meters: float) -> float:
        R = 6378137.0
        lat_rad = math.radians(lat)
        resolution = (math.cos(lat_rad) * 2 * math.pi * R) / (self.tile_size * 2 ** self.zoom)
        return meters / resolution

    # ================= tile management =================
    def _load_tile(self, x: int, y: int) -> np.ndarray:
        try:
            url = self.tile_server.format(z=self.zoom, x=x, y=y)
            r = self.session.get(url, timeout=3)
            if r.status_code == 200:
                data = np.frombuffer(r.content, dtype=np.uint8)
                return cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception:
            pass
        # 실패 시 회색 타일
        return np.full((self.tile_size, self.tile_size, 3), 200, dtype=np.uint8)

    def _ensure_buffer(self, tile_x: float, tile_y: float):
        # 3x3 타일 버퍼 갱신
        self.buffer_image.fill(200)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                tx, ty = int(tile_x) + dx, int(tile_y) + dy
                if (tx, ty) not in self.tile_buffer:
                    self.tile_buffer[(tx, ty)] = self._load_tile(tx, ty)
                tile_img = self.tile_buffer[(tx, ty)]
                y0, x0 = (dy + 1) * self.tile_size, (dx + 1) * self.tile_size
                self.buffer_image[y0:y0+self.tile_size, x0:x0+self.tile_size] = tile_img
        # 버퍼 밖 타일 제거
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
        # buffer_image에서 display_size 영역 잘라서 반환
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

    def _compute_shape_pixels(self, lat: float, lon: float, yaw: float, alt: float, half_fov: float) -> Tuple[int,int,int]:
        """
        lat/lon, yaw, alt -> local pixel (cx, cy)와 탐지 반경 r_px 계산
        """
        ex, ey = self._latlon_to_local(lat, lon)
        detect_m = alt * math.tan(half_fov)
        full_r_px = self._meters_to_pixels(lat, detect_m)
        # 원형 예시: 반으로 축소
        r_px = int(full_r_px * 0.5)
        # 드론 아이콘 위치 offset (alt 높이를 반영해 약간 띄움)
        off_px = self._meters_to_pixels(lat, alt)
        cx = int(ex + off_px * math.cos(math.radians(yaw)))
        cy = int(ey - off_px * math.sin(math.radians(yaw)))
        return cx, cy, r_px

    # ================= update_map =================
    def update_map(self, center: List[float], extras: List, poi: Optional[List[float]] = None) -> np.ndarray:
        """
        center: [lat, lon, yaw_deg, alt_m]
        extras: ["Name", lat, lon, yaw, alt, ...]
        poi: [lat, lon] or None
        """
        # 1) POI 저장
        if poi is not None:
            self.poi = list(poi)

        # 2) 입력 변경 캐시 확인
        curr_inputs = (tuple(center), tuple(extras), tuple(self.poi) if self.poi else None)
        if curr_inputs != self.prev_inputs:
            self.prev_inputs = curr_inputs
            # center가 크게 변경되어 뷰가 이동할 때는
            # self.global_count_mask, self.visited_mask, self.prev_frame_mask 을
            # 재계산하거나 shift해야 함. 여기선 고정 center 용 예시이므로 생략.

        # 3) 지도 중심 업데이트
        lat_c, lon_c, yaw_c, alt_c = center
        self._update_center(lat_c, lon_c)

        # 4) 베이스 프레임
        frame = self._render_base()
        h, w = frame.shape[:2]

        # 5) global_count_mask 초기화 (첫 호출 시)
        if self.global_count_mask is None:
            self.global_count_mask = np.zeros((h, w), dtype=np.int32)

        # 6) FOV 절반 각 (예: 82.6도)
        FOV_DEG = 82.6
        half_fov = math.radians(FOV_DEG / 2)

        # 7) 현재 프레임 탐지 정보 수집
        # 리스트: (drone_id, lat, lon, yaw, alt)
        current_entries: List[Tuple[str, float, float, float, float]] = []
        current_entries.append(('main', lat_c, lon_c, yaw_c, alt_c))
        for i in range(0, len(extras), 5):
            name = extras[i]
            lat_e = extras[i+1]
            lon_e = extras[i+2]
            yaw_e = extras[i+3]
            alt_e = extras[i+4]
            current_entries.append((name, lat_e, lon_e, yaw_e, alt_e))

        # 8) 드론별 current_mask 계산 및 new_visit 처리
        for (drone_id, lat_h, lon_h, yaw_h, alt_h) in current_entries:
            # current detection mask 생성
            cx, cy, r_px = self._compute_shape_pixels(lat_h, lon_h, yaw_h, alt_h, half_fov)
            # current_mask: bool mask of shape (h,w)
            current_mask = np.zeros((h, w), dtype=bool)
            if r_px > 0:
                y0 = max(0, cy - r_px)
                y1 = min(h, cy + r_px + 1)
                x0 = max(0, cx - r_px)
                x1 = min(w, cx + r_px + 1)
                yy, xx = np.ogrid[y0:y1, x0:x1]
                dist2 = (yy - cy)**2 + (xx - cx)**2
                circle_mask = dist2 <= r_px**2
                current_mask[y0:y1, x0:x1] = circle_mask

            # visited_mask, prev_frame_mask 초기화 검사
            if drone_id not in self.visited_mask:
                # 처음 등장 시, 크기에 맞춰 False mask 생성
                self.visited_mask[drone_id] = np.zeros((h, w), dtype=bool)
                self.prev_frame_mask[drone_id] = np.zeros((h, w), dtype=bool)
            else:
                # 만약 이전에 저장된 mask shape이 다르면(보통 display_size 고정이므로 없음), 재초기화 필요
                vm = self.visited_mask[drone_id]
                if vm.shape != (h, w):
                    self.visited_mask[drone_id] = np.zeros((h, w), dtype=bool)
                    self.prev_frame_mask[drone_id] = np.zeros((h, w), dtype=bool)

            prev_mask = self.prev_frame_mask[drone_id]
            visited = self.visited_mask[drone_id]

            # new_visit_mask: 직전 프레임에는 탐지 안 했으나 이번에 탐지된 픽셀
            new_visit_mask = current_mask & (~prev_mask)
            if np.any(new_visit_mask):
                # 각 픽셀별 처리: first visit or revisit 모두 카운트 증가
                # visited==False: 첫 방문; visited==True: 재방문
                # global_count_mask에 +1
                # numpy indexing
                self.global_count_mask[new_visit_mask] += 1
                # visited mask 갱신: 이제 방문 이력이 생기거나 이미 있었음
                visited[new_visit_mask] = True

            # prev_frame_mask 업데이트: 다음 프레임 비교용
            self.prev_frame_mask[drone_id] = current_mask

        # 9) 시각화: global_count_mask 기반 alpha overlay
        frame_f = frame.astype(np.float32) / 255.0
        base_alpha = 0.2  # 한 번 방문 시 alpha. 필요에 따라 조정(0.1~0.3 등)
        # alpha_map: float32 (h,w), alpha = base_alpha * count, 클리핑 0~1
        alpha_map = self.global_count_mask.astype(np.float32) * base_alpha
        np.clip(alpha_map, 0.0, 1.0, out=alpha_map)

        if np.any(alpha_map > 0):
            overlay = np.zeros_like(frame_f)
            # 빨간색 overlay normalized
            overlay[..., 0] = 0.0
            overlay[..., 1] = 0.0
            overlay[..., 2] = 1.0
            alpha_3c = alpha_map[..., None]  # (h,w,1)
            frame_f = frame_f * (1.0 - alpha_3c) + overlay * alpha_3c

        frame = (np.clip(frame_f, 0.0, 1.0) * 255).astype(np.uint8)

        # 10) 드론 아이콘 그리기 (빨간색 통일)
        ex_c = w // 2
        ey_c = h // 2
        # main 드론: 화면 중앙
        self._draw_iso_triangle(frame, (ex_c, ey_c), yaw_c, 6, (0, 0, 255))
        # extras 드론
        for i in range(0, len(extras), 5):
            lat_e = extras[i+1]
            lon_e = extras[i+2]
            yaw_e = extras[i+3]
            pos = self._latlon_to_local(lat_e, lon_e)
            self._draw_iso_triangle(frame, pos, yaw_e, 5, (0, 0, 255))

        # 11) POI 표시
        if self.poi:
            px, py = self._latlon_to_local(self.poi[0], self.poi[1])
            cv2.circle(frame, (px, py), 3, (0, 255, 0), -1)

        # 12) 최종 리사이즈
        self.map_img = cv2.resize(frame, (360, 360), interpolation=cv2.INTER_LINEAR)
        return self.map_img

    def get_map(self) -> np.ndarray:
        return self.map_img

# ================= main 시뮬레이션 예시 =================
def main():
    # MAP 인스턴스 생성
    m = MAP(zoom=18)

    # 고정 center 예시: 서울 시청 부근
    center = [37.5665, 126.9780, 0.0, 10.0]  # [lat, lon, yaw_deg, alt_m]
    # extras 드론 초기 정보: ["Name", lat, lon, yaw, alt]
    extras = [
        "DroneA", 37.56652, 126.97802, 45.0, 12.0,
        "DroneB", 37.56648, 126.97798, 135.0, 8.0
    ]

    print("MAP 시뮬레이션 시작. ESC 누르면 종료.")

    # 시뮬레이션 루프
    speed = 3.0   # m/s 예시 속도
    fps = 10.0    # 프레임 속도
    R = 6378137.0
    dt = 1.0 / fps

    while True:
        # 드론 위치 갱신 예시: extras만 움직이기
        for i in range(0, len(extras), 5):
            yaw = extras[i+3]
            yaw = (yaw + 5.0) % 360.0
            extras[i+3] = yaw
            dy_e = speed * dt * math.sin(math.radians(yaw))
            dx_e = speed * dt * math.cos(math.radians(yaw))
            lat_e = extras[i+1] + (dy_e / R) * (180.0 / math.pi)
            lon_e = extras[i+2] + (dx_e / (R * math.cos(math.radians(lat_e)))) * (180.0 / math.pi)
            extras[i+1] = lat_e
            extras[i+2] = lon_e

        # MAP 업데이트 및 표시
        frame = m.update_map(center, extras)
        cv2.imshow("Map Test", frame)

        # ESC 눌러 종료
        key = cv2.waitKey(int(1000.0 / fps)) & 0xFF
        if key == 27:
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
