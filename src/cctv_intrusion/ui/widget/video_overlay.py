"""영상 위 위험구역·사람 탐지 박스·경보 상태 그리기."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF

from cctv_intrusion.detection import Detection
from cctv_intrusion.intrusion import STATE_LABELS, MonitorState
from cctv_intrusion.ui.styles import colors
from cctv_intrusion.zone import Zone, format_level

POINT_RADIUS = 5
STATUS_MARGIN = 12
STATUS_PAD_X = 14
STATUS_PAD_Y = 8
# 선 두께 (기존 대비 YOLO·구역 ≈2/3, 경보 테두리 ≈1/2)
PERSON_BOX_WIDTH = 1.5
ZONE_EDGE_WIDTH = 1.5
ZONE_SELECTED_WIDTH = 2.5
ALARM_FRAME_WIDTH = 2
ALARM_WASH_ALPHA = 18


def to_view_polygon(points: list[tuple[float, float]], scale: float) -> QPolygonF:
    return QPolygonF([QPointF(x * scale, y * scale) for x, y in points])


def draw_zone_name(painter: QPainter, name: str, polygon: QPolygonF, color: QColor) -> None:
    font = painter.font()
    font.setPixelSize(16)
    font.setBold(True)
    painter.setFont(font)

    text_rect = painter.fontMetrics().boundingRect(name).adjusted(-6, -3, 6, 3)
    text_rect.moveCenter(polygon.boundingRect().center().toPoint())

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawRect(text_rect)
    painter.setPen(colors.ZONE_NAME_TEXT)
    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, name)


def draw_alarm_frame(pixmap: QPixmap) -> None:
    """경보 중 빨간 반투명 덮개 + 얇은 테두리로 가시성을 높인다."""
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    wash = QColor(colors.ALARM_FRAME)
    wash.setAlpha(ALARM_WASH_ALPHA)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(wash)
    painter.drawRect(QRectF(0, 0, pixmap.width(), pixmap.height()))

    pen = QPen(colors.ALARM_FRAME, ALARM_FRAME_WIDTH)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    inset = ALARM_FRAME_WIDTH / 2
    painter.drawRect(
        QRectF(inset, inset, pixmap.width() - ALARM_FRAME_WIDTH, pixmap.height() - ALARM_FRAME_WIDTH)
    )
    painter.end()


def draw_monitor_state(pixmap: QPixmap, state: MonitorState) -> None:
    """영상 우측 상단에 경보 상태 배지를 그린다. 경보 중이면 빨간 테두리도 표시."""
    if state == MonitorState.ALARM:
        draw_alarm_frame(pixmap)

    label = STATE_LABELS.get(state, str(state))
    text = f"상태  {label}"
    bg = colors.MONITOR_STATE_COLORS.get(state.value, colors.MONITOR_STATE_COLORS["idle"])

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = painter.font()
    font.setPixelSize(18)
    font.setBold(True)
    painter.setFont(font)

    metrics = painter.fontMetrics()
    text_w = metrics.horizontalAdvance(text)
    text_h = metrics.height()
    box_w = text_w + STATUS_PAD_X * 2
    box_h = text_h + STATUS_PAD_Y * 2
    x = pixmap.width() - box_w - STATUS_MARGIN
    y = STATUS_MARGIN
    rect = QRectF(x, y, box_w, box_h)

    if state == MonitorState.ALARM:
        # 경보 배지: 더 진한 빨강 + 흰 테두리로 눈에 띄게
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(colors.ALARM_BADGE)
    else:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
    painter.drawRoundedRect(rect, 8, 8)
    painter.setPen(colors.MONITOR_STATE_TEXT)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    painter.end()


def draw_zones(
    pixmap: QPixmap,
    zones: list[Zone],
    *,
    selected_index: int,
    scale: float,
    drawing: bool,
    drawing_points: list[tuple[int, int]],
) -> None:
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    for i, zone in enumerate(zones):
        selected = i == selected_index
        color = colors.zone_color(zone.level)
        polygon = to_view_polygon(zone.points, scale)

        edge = colors.ZONE_SELECTED if selected else color
        painter.setPen(QPen(edge, ZONE_SELECTED_WIDTH if selected else ZONE_EDGE_WIDTH))
        fill = QColor(color)
        fill.setAlpha(120 if selected else 55)
        painter.setBrush(fill)
        painter.drawPolygon(polygon)

        label = f"{zone.name}  ·  {format_level(zone.level)}"
        draw_zone_name(painter, label, polygon, color)

    if drawing and drawing_points:
        points = to_view_polygon(drawing_points, scale)
        painter.setPen(QPen(colors.ZONE_DRAWING, ZONE_EDGE_WIDTH))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline(points)
        if len(points) >= 3:
            painter.setPen(QPen(colors.ZONE_DRAWING, ZONE_EDGE_WIDTH, Qt.PenStyle.DashLine))
            painter.drawLine(points[len(points) - 1], points[0])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colors.ZONE_DRAWING)
        for point in points:
            painter.drawEllipse(point, POINT_RADIUS, POINT_RADIUS)

    painter.end()


def draw_detections(pixmap: QPixmap, detections: list[Detection], scale: float) -> None:
    if not detections:
        return
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(colors.PERSON_BOX, PERSON_BOX_WIDTH))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for detection in detections:
        painter.drawRect(
            QRectF(
                detection.x1 * scale,
                detection.y1 * scale,
                (detection.x2 - detection.x1) * scale,
                (detection.y2 - detection.y1) * scale,
            )
        )
    painter.end()
