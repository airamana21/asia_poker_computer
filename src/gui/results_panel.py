from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel,
                               QScrollArea, QVBoxLayout, QWidget)

from ..core.cards import Card
from .assets import asset_path, CARD_W, CARD_H


class ResultsPanel(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        container = QWidget()
        self.v = QVBoxLayout(container)
        self.setWidget(container)
        self._scale = 1.0
        self._entries: List[tuple[str, Tuple[Card, ...], Tuple[Card, ...], Tuple[Card, ...], float]] = []
        self._card_ratio = 0.65
        self._title_base_pt: float | None = None
        self._group_base_pt: float | None = None

    def show_result(
        self,
        title: str,
        hi: Sequence[Card],
        mid: Sequence[Card],
        low: Sequence[Card],
        win_rate: float,
    ):
        entry = (
            title,
            tuple(hi),
            tuple(mid),
            tuple(low),
            win_rate,
        )
        self._entries.append(entry)
        self._render_entry(entry)

    def clear_results(self):
        self._entries.clear()
        self._remove_widgets()

    def set_scale(self, scale: float):
        if abs(scale - self._scale) < 1e-3:
            return
        self._scale = scale
        self._rerender()

    def _remove_widgets(self):
        while self.v.count():
            item = self.v.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

    def _rerender(self):
        self._remove_widgets()
        for entry in self._entries:
            self._render_entry(entry)

    def _render_entry(self, entry: tuple[str, Tuple[Card, ...], Tuple[Card, ...], Tuple[Card, ...], float]):
        title, hi, mid, low, win_rate = entry
        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(
            int(10 * self._scale),
            int(8 * self._scale),
            int(10 * self._scale),
            int(8 * self._scale),
        )
        lay.setSpacing(int(6 * self._scale))

        title_label = QLabel(f"{title} — Win 2 of 3: {win_rate:.2%}")
        self._set_font_size(title_label, "title")
        lay.addWidget(title_label)

        for label_text, group in ("4-card", hi), ("2-card", mid), ("1-card", low):
            row = QHBoxLayout()
            row.setSpacing(int(6 * self._scale))
            tag = QLabel(label_text)
            self._set_font_size(tag, "group")
            row.addWidget(tag)
            for card in group:
                pix = QPixmap(asset_path(card)).scaled(
                    int(CARD_W * self._card_ratio * self._scale),
                    int(CARD_H * self._card_ratio * self._scale),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                lab = QLabel()
                lab.setPixmap(pix)
                row.addWidget(lab)
            lay.addLayout(row)
        self.v.addWidget(box)

    def _set_font_size(self, label: QLabel, kind: str):
        font = label.font()
        base = font.pointSizeF()
        if base <= 0:
            base = float(font.pointSize() if font.pointSize() > 0 else 10)
        if kind == "title":
            if self._title_base_pt is None:
                self._title_base_pt = base
            target = self._title_base_pt * self._scale
        else:
            if self._group_base_pt is None:
                self._group_base_pt = base
            target = self._group_base_pt * self._scale
        font.setPointSizeF(max(6.0, target))
        label.setFont(font)
