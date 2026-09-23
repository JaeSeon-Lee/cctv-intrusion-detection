import json
import cv2
import numpy as np


class ZoneEditor:
    """
    마우스로 다각형 위험구역을 그리고 JSON으로 저장/불러오기 하는 클래스.

    조작법:
      - 좌클릭: 점 추가
      - 화면 하단 버튼(사각형 영역) 클릭 또는 키보드로 완료/저장/초기화
      - 키보드: n = 새 구역 시작, s = 저장, r = 초기화, ESC = 종료
    """

    def __init__(self, window_name: str = "Zone Editor"):
        self.window_name = window_name
        self.zones: list[dict] = []          # 완성된 구역들
        self.current_points: list[list[int]] = []  # 그리는 중인 다각형 점들
        self.zone_count = 0

        # "버튼" 영역 정의 (x1, y1, x2, y2)
        self.buttons = {
            "완료": (10, 10, 100, 50),
            "저장": (110, 10, 200, 50),
            "초기화": (210, 10, 300, 50),
        }

        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self._on_mouse)

    # ---------- 마우스 콜백 ----------
    def _on_mouse(self, event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return

        # 버튼 영역 클릭인지 먼저 체크
        clicked_button = self._check_button_click(x, y)
        if clicked_button:
            self._handle_button(clicked_button)
            return

        # 버튼이 아니면 다각형 점 추가
        self.current_points.append([x, y])

    def _check_button_click(self, x: int, y: int) -> str | None:
        for name, (bx1, by1, bx2, by2) in self.buttons.items():
            if bx1 <= x <= bx2 and by1 <= y <= by2:
                return name
        return None

    def _handle_button(self, name: str) -> None:
        if name == "완료":
            self._finish_zone()
        elif name == "저장":
            self.save("zones.json")
            print("저장 완료: zones.json")
        elif name == "초기화":
            self.current_points = []

    # ---------- 키보드 처리 (main 루프에서 호출) ----------
    def handle_key(self, key: int) -> None:
        if key == ord("n"):  # 완료
            self._finish_zone()
        elif key == ord("s"):  # 저장
            self.save("zones.json")
            print("저장 완료: zones.json")
        elif key == ord("r"):  # 초기화
            self.current_points = []

    def _finish_zone(self) -> None:
        if len(self.current_points) < 3:
            print("점이 3개 이상 있어야 다각형이 됩니다.")
            return

        self.zone_count += 1
        self.zones.append(
            {
                "name": f"zone_{self.zone_count}",
                "points": self.current_points,
                "level": "위험",
            }
        )
        self.current_points = []

    # ---------- 저장 / 불러오기 ----------
    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.zones, f, ensure_ascii=False, indent=2)

    def load(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            self.zones = json.load(f)

    # ---------- 화면 그리기 ----------
    def draw(self, frame: np.ndarray) -> np.ndarray:
        # 완성된 구역들
        for zone in self.zones:
            pts = np.array(zone["points"], np.int32)
            cv2.polylines(frame, [pts], True, (0, 255, 255), 2)
            cv2.putText(frame, zone["name"], tuple(pts[0]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # 그리는 중인 다각형
        if self.current_points:
            pts = np.array(self.current_points, np.int32)
            cv2.polylines(frame, [pts], False, (0, 0, 255), 2)
            for p in self.current_points:
                cv2.circle(frame, tuple(p), 4, (0, 0, 255), -1)

        # 버튼 그리기
        for name, (x1, y1, x2, y2) in self.buttons.items():
            cv2.rectangle(frame, (x1, y1), (x2, y2), (50, 50, 50), -1)
            cv2.putText(frame, name, (x1 + 10, y1 + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        return frame