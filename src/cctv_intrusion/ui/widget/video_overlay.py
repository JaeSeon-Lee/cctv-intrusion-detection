"""영상 위 위험구역·사람 탐지 박스 그리기."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF

from cctv_intrusion.detection import Detection
from cctv_intrusion.ui.styles import colors
from cctv_intrusion.zone import Zone, format_level

POINT_RADIUS = 5


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
        painter.setPen(QPen(edge, 4 if selected else 2))
        fill = QColor(color)
        fill.setAlpha(120 if selected else 55)
        painter.setBrush(fill)
        painter.drawPolygon(polygon)

        label = f"{zone.name}  ·  {format_level(zone.level)}"
        draw_zone_name(painter, label, polygon, color)

    if drawing and drawing_points:
        points = to_view_polygon(drawing_points, scale)
        painter.setPen(QPen(colors.ZONE_DRAWING, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline(points)
        if len(points) >= 3:
            painter.setPen(QPen(colors.ZONE_DRAWING, 2, Qt.PenStyle.DashLine))
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
    painter.setPen(QPen(colors.PERSON_BOX, 2))
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
