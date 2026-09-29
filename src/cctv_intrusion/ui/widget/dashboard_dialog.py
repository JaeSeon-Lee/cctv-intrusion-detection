"""상시 녹화 침입 대시보드 창.

events.csv 기준으로 상시 녹화(camN/*.ts) 한 개의
- 녹화 길이 대비 침입 비율(%) · 침입 횟수 · 평균/최장 지속 (요약 타일)
- 녹화 타임라인 위 침입 구간
- 침입별 지속 시간 막대 그래프
- 사건 표
를 한 화면에 보여준다.
"""

from __future__ import annotations

from pathlib import Path
from typing import override

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from cctv_intrusion.intrusion.events import format_video_timestamp
from cctv_intrusion.intrusion.recording_stats import RecordingStats, recording_stats
from cctv_intrusion.ui.styles import load_qss
from cctv_intrusion.ui.styles.colors import (
    CHART_AXIS_TEXT,
    CHART_GRID,
    CHART_INTRUSION,
    CHART_INTRUSION_HOVER,
    CHART_LABEL_BG,
    CHART_TRACK,
)
from cctv_intrusion.zone.levels import get_level

EMPTY_TEXT = "이 녹화에 기록된 침입(events.csv)이 없습니다."


def format_seconds(seconds: float) -> str:
    return f"{seconds:.2f}초"


def format_clock(seconds: float) -> str:
    """축 눈금용 짧은 시각 (M:SS)."""
    total = int(round(max(0.0, seconds)))
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"


def level_label(level_id: str) -> str:
    return get_level(level_id).label if level_id else "-"


def _nice_step(max_value: float, target_ticks: int = 4) -> float:
    """눈금 간격 (1·2·5 × 10^n)."""
    if max_value <= 0:
        return 1.0
    raw = max_value / target_ticks
    magnitude = 10 ** int(f"{raw:e}".split("e")[1])
    for factor in (1, 2, 5, 10):
        if raw <= factor * magnitude:
            return factor * magnitude
    return 10 * magnitude


def _axis_font(widget: QWidget) -> QFont:
    font = QFont(widget.font())
    font.setPixelSize(11)
    return font


class StatTile(QFrame):
    """요약 숫자 한 칸 (제목 · 값 · 보조 설명)."""

    def __init__(self, caption: str, value: str, detail: str = "") -> None:
        super().__init__()
        self.setObjectName("statTile")
        caption_label = QLabel(caption)
        caption_label.setObjectName("statCaption")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("statValue")
        self.detail_label = QLabel(detail)
        self.detail_label.setObjectName("statDetail")
        self.detail_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)
        layout.addWidget(caption_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)


class IntrusionTimeline(QWidget):
    """영상 전체 길이 막대 위에 침입 구간을 칠한다. 구간에 마우스를 올리면 상세 표시."""

    TRACK_HEIGHT = 22
    PAD_X = 12

    def __init__(self, stats: RecordingStats) -> None:
        super().__init__()
        self.stats = stats
        self._hover = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(64)

    def _track_rect(self) -> QRectF:
        return QRectF(self.PAD_X, 10, self.width() - 2 * self.PAD_X, self.TRACK_HEIGHT)

    def _span_rect(self, index: int) -> QRectF:
        track = self._track_rect()
        total = self.stats.video_sec or 1.0
        event = self.stats.events[index]
        x1 = track.left() + track.width() * min(1.0, max(0.0, event.alarm_sec / total))
        x2 = track.left() + track.width() * min(1.0, max(0.0, event.cleared_sec / total))
        # 아주 짧은 사건도 보이도록 최소 3px
        return QRectF(x1, track.top(), max(3.0, x2 - x1), track.height())

    @override
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = self._track_rect()

        path = QPainterPath()
        path.addRoundedRect(track, 4, 4)
        painter.fillPath(path, CHART_TRACK)
        painter.setClipPath(path)
        for index in range(self.stats.count):
            color = CHART_INTRUSION_HOVER if index == self._hover else CHART_INTRUSION
            painter.fillRect(self._span_rect(index), color)
        painter.setClipping(False)

        # 시간 눈금
        painter.setFont(_axis_font(self))
        total = self.stats.video_sec
        step = _nice_step(total, 6)
        tick = 0.0
        while total > 0 and tick <= total + 1e-6:
            x = track.left() + track.width() * tick / total
            painter.setPen(QPen(CHART_GRID, 1))
            painter.drawLine(QPointF(x, track.bottom() + 2), QPointF(x, track.bottom() + 6))
            painter.setPen(CHART_AXIS_TEXT)
            text_rect = QRectF(x - 30, track.bottom() + 8, 60, 16)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter, format_clock(tick))
            tick += step

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        hover = -1
        for index in range(self.stats.count):
            if self._span_rect(index).adjusted(-3, -6, 3, 6).contains(pos):
                hover = index
                break
        if hover != self._hover:
            self._hover = hover
            self.update()
        if hover >= 0:
            e = self.stats.events[hover]
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"#{hover + 1}  {format_video_timestamp(e.alarm_sec)} → "
                f"{format_video_timestamp(e.cleared_sec)}\n"
                f"지속 {format_seconds(e.duration_sec)} · {e.zone_name}",
                self,
            )
        else:
            QToolTip.hideText()

    @override
    def leaveEvent(self, event) -> None:
        self._hover = -1
        self.update()
        super().leaveEvent(event)


class DurationBarChart(QWidget):
    """침입 한 건당 지속 시간 막대 그래프 (평균선 포함)."""

    LEFT = 44
    RIGHT = 12
    TOP = 22
    BOTTOM = 26
    MAX_BAR_WIDTH = 48
    # 막대가 이보다 많으면 값 라벨은 최장 막대에만 단다
    LABEL_ALL_LIMIT = 12

    def __init__(self, stats: RecordingStats) -> None:
        super().__init__()
        self.stats = stats
        self._hover = -1
        self.setMouseTracking(True)
        self.setMinimumSize(280, 220)

    def _plot_rect(self) -> QRectF:
        return QRectF(
            self.LEFT,
            self.TOP,
            max(1.0, self.width() - self.LEFT - self.RIGHT),
            max(1.0, self.height() - self.TOP - self.BOTTOM),
        )

    def _y_max(self) -> tuple[float, float]:
        step = _nice_step(self.stats.max_sec, 4)
        top = step * max(1, int(self.stats.max_sec / step + 0.999))
        if top < self.stats.max_sec * 1.08:
            top += step
        return top, step

    def _bar_rect(self, index: int) -> QRectF:
        plot = self._plot_rect()
        slot = plot.width() / max(1, self.stats.count)
        width = min(self.MAX_BAR_WIDTH, max(2.0, slot * 0.6))
        y_max, _ = self._y_max()
        height = plot.height() * self.stats.durations[index] / y_max
        x = plot.left() + slot * index + (slot - width) / 2
        return QRectF(x, plot.bottom() - height, width, height)

    @override
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(_axis_font(self))
        plot = self._plot_rect()

        if not self.stats.events:
            painter.setPen(CHART_AXIS_TEXT)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, EMPTY_TEXT)
            return

        # y 격자 + 눈금 (초)
        y_max, step = self._y_max()
        value = 0.0
        while value <= y_max + 1e-6:
            y = plot.bottom() - plot.height() * value / y_max
            painter.setPen(QPen(CHART_GRID, 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(CHART_AXIS_TEXT)
            painter.drawText(
                QRectF(0, y - 8, self.LEFT - 8, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{value:g}s",
            )
            value += step

        label_all = self.stats.count <= self.LABEL_ALL_LIMIT
        longest = self.stats.durations.index(self.stats.max_sec)
        slot = plot.width() / self.stats.count
        for index in range(self.stats.count):
            bar = self._bar_rect(index)
            color = CHART_INTRUSION_HOVER if index == self._hover else CHART_INTRUSION
            # 위쪽 끝만 둥글게 (4px), 아래는 기준선에 붙인다
            path = QPainterPath()
            path.setFillRule(Qt.FillRule.WindingFill)
            radius = min(4.0, bar.width() / 2, bar.height())
            path.addRoundedRect(bar, radius, radius)
            path.addRect(QRectF(bar.left(), bar.bottom() - radius, bar.width(), radius))
            painter.fillPath(path, color)

            painter.setPen(CHART_AXIS_TEXT)
            if label_all or index == longest:
                painter.drawText(
                    QRectF(bar.center().x() - 30, bar.top() - 18, 60, 16),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                    f"{self.stats.durations[index]:.2f}s",
                )
            if label_all or index in (0, self.stats.count - 1):
                painter.drawText(
                    QRectF(plot.left() + slot * index, plot.bottom() + 6, slot, 16),
                    Qt.AlignmentFlag.AlignHCenter,
                    f"#{index + 1}",
                )

        # 평균선
        avg_y = plot.bottom() - plot.height() * self.stats.avg_sec / y_max
        pen = QPen(QColor(CHART_AXIS_TEXT), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(plot.left(), avg_y), QPointF(plot.right(), avg_y))
        # 막대와 겹쳐도 읽히도록 라벨 뒤에 바탕색을 깐다
        avg_text = f"평균 {self.stats.avg_sec:.2f}s"
        text_width = painter.fontMetrics().horizontalAdvance(avg_text) + 8
        label_rect = QRectF(plot.right() - text_width, avg_y - 18, text_width, 16)
        painter.fillRect(label_rect, CHART_LABEL_BG)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, avg_text)

        # 기준선
        painter.setPen(QPen(CHART_AXIS_TEXT, 1))
        painter.drawLine(QPointF(plot.left(), plot.bottom()), QPointF(plot.right(), plot.bottom()))

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self.stats.events:
            return
        plot = self._plot_rect()
        pos = event.position()
        hover = -1
        # 막대보다 넓은 슬롯 전체를 hover 영역으로
        if plot.left() <= pos.x() <= plot.right() and plot.top() <= pos.y() <= plot.bottom():
            slot = plot.width() / self.stats.count
            hover = min(self.stats.count - 1, int((pos.x() - plot.left()) / slot))
        if hover != self._hover:
            self._hover = hover
            self.update()
        if hover >= 0:
            e = self.stats.events[hover]
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"#{hover + 1}  지속 {format_seconds(e.duration_sec)}\n"
                f"{format_video_timestamp(e.alarm_sec)} → {format_video_timestamp(e.cleared_sec)}"
                f" · {e.zone_name}",
                self,
            )
        else:
            QToolTip.hideText()

    @override
    def leaveEvent(self, event) -> None:
        self._hover = -1
        self.update()
        super().leaveEvent(event)


def _section(title: str, body: QWidget, subtitle: str = "") -> QFrame:
    frame = QFrame()
    frame.setObjectName("section")
    title_label = QLabel(title)
    title_label.setObjectName("sectionTitle")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(6)
    header = QHBoxLayout()
    header.addWidget(title_label)
    header.addStretch(1)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setObjectName("sectionSubtitle")
        header.addWidget(sub)
    layout.addLayout(header)
    layout.addWidget(body, 1)
    return frame


class DashboardDialog(QDialog):
    """상시 녹화 한 개의 침입 대시보드."""

    TABLE_HEADERS = ("#", "경보", "해제", "지속(초)", "구역", "등급", "클립")

    def __init__(
        self,
        recording_path: str | Path,
        parent: QWidget | None = None,
        *,
        stats: RecordingStats | None = None,
        live: bool = False,
    ) -> None:
        super().__init__(parent)
        recording = Path(recording_path)
        self.stats = stats if stats is not None else recording_stats(recording)
        stats = self.stats
        name = f"{recording.parent.name}/{recording.name}"

        self.setObjectName("dashboard")
        self.setWindowTitle(f"대시보드 — {name}")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(1100, 740)
        self.setStyleSheet(load_qss("dashboard"))

        title = QLabel("침입 대시보드")
        title.setObjectName("dashTitle")
        notes = [f"{name} · 녹화 길이 {format_seconds(stats.video_sec)}"]
        if live:
            notes.append("녹화 중 — 창을 연 시점까지 집계")
        if stats.unplaced_count:
            notes.append(f"녹화 위치가 없는 이전 기록 {stats.unplaced_count}건은 제외")
        subtitle = QLabel(" · ".join(notes))
        subtitle.setObjectName("dashSubtitle")

        self.ratio_tile = StatTile(
            "침입 비율",
            f"{stats.ratio_pct:.1f}%",
            f"침입 {format_seconds(stats.intrusion_sec)} / 녹화 {format_seconds(stats.video_sec)}",
        )
        self.count_tile = StatTile("침입 횟수", f"{stats.count}건", "events.csv 기준")
        self.avg_tile = StatTile(
            "평균 지속 시간",
            format_seconds(stats.avg_sec),
            f"최단 {format_seconds(stats.min_sec)}" if stats.events else "-",
        )
        self.max_tile = StatTile(
            "최장 지속 시간",
            format_seconds(stats.max_sec),
            f"#{stats.durations.index(stats.max_sec) + 1}" if stats.events else "-",
        )
        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        for tile in (self.ratio_tile, self.count_tile, self.avg_tile, self.max_tile):
            tiles.addWidget(tile, 1)

        self.timeline = IntrusionTimeline(stats)
        timeline_section = _section(
            "녹화 타임라인",
            self.timeline,
            f"빨간 구간 = 침입 ({stats.ratio_pct:.1f}%)",
        )

        self.bar_chart = DurationBarChart(stats)
        chart_section = _section("침입별 지속 시간", self.bar_chart, "점선 = 평균")

        self.table = self._build_table(stats)
        table_section = _section("사건 목록", self.table)

        bottom = QHBoxLayout()
        bottom.setSpacing(12)
        bottom.addWidget(chart_section, 3)
        bottom.addWidget(table_section, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(tiles)
        layout.addWidget(timeline_section)
        layout.addLayout(bottom, 1)

    def _build_table(self, stats: RecordingStats) -> QTableWidget:
        table = QTableWidget(stats.count, len(self.TABLE_HEADERS))
        table.setObjectName("eventsTable")
        table.setHorizontalHeaderLabels(self.TABLE_HEADERS)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        for row, event in enumerate(stats.events):
            values = (
                str(row + 1),
                format_video_timestamp(event.alarm_sec),
                format_video_timestamp(event.cleared_sec),
                f"{event.duration_sec:.2f}",
                event.zone_name or "-",
                level_label(event.zone_level),
                event.clip_file or "-",
            )
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                if column != 4:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, column, item)
        return table
