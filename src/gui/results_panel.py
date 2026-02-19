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
        self._card_ratio = 0.65
        self._title_base_pt: float | None = None
        self._group_base_pt: float | None = None

        # House Way state
        self._hw_hi: Tuple[Card, ...] | None = None
        self._hw_mid: Tuple[Card, ...] | None = None
        self._hw_low: Tuple[Card, ...] | None = None
        self._hw_win_rate: float | None = None
        self._hw_is_best: bool = False

        # Simulation result entries: (title, hi, mid, low, win_rate)
        self._sim_entries: List[Tuple[str, Tuple[Card, ...], Tuple[Card, ...], Tuple[Card, ...], float]] = []

    # ── Public API ──────────────────────────────────────────

    def show_house_way(
        self,
        hi: Sequence[Card],
        mid: Sequence[Card],
        low: Sequence[Card],
    ):
        """Display the House Way arrangement at the top of the results area."""
        self._hw_hi = tuple(hi)
        self._hw_mid = tuple(mid)
        self._hw_low = tuple(low)
        self._hw_win_rate = None
        self._hw_is_best = False
        self._rerender()

    def mark_house_way_as_best(self, win_rate: float):
        """Update the House Way entry to indicate it equals the simulated best."""
        self._hw_win_rate = win_rate
        self._hw_is_best = True
        self._rerender()

    def show_result(
        self,
        title: str,
        hi: Sequence[Card],
        mid: Sequence[Card],
        low: Sequence[Card],
        win_rate: float,
    ):
        """Append a simulation result entry below the House Way."""
        self._sim_entries.append((title, tuple(hi), tuple(mid), tuple(low), win_rate))
        self._rerender()

    def clear_sim_results(self):
        """Clear only simulation results, preserving the House Way."""
        self._sim_entries.clear()
        self._hw_win_rate = None
        self._hw_is_best = False
        self._rerender()

    def clear_results(self):
        """Clear everything (House Way + simulation results)."""
        self._hw_hi = self._hw_mid = self._hw_low = None
        self._hw_win_rate = None
        self._hw_is_best = False
        self._sim_entries.clear()
        self._remove_widgets()

    def set_scale(self, scale: float):
        if abs(scale - self._scale) < 1e-3:
            return
        self._scale = scale
        self._rerender()

    # ── Internal rendering ──────────────────────────────────

    def _remove_widgets(self):
        while self.v.count():
            item = self.v.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

    def _rerender(self):
        self._remove_widgets()

        # 1. House Way entry (always first)
        if self._hw_hi is not None:
            if self._hw_is_best and self._hw_win_rate is not None:
                hw_title = f"House Way = Best — Win 2 of 3: {self._hw_win_rate:.2%}"
            else:
                hw_title = "House Way"
            self._render_entry(hw_title, self._hw_hi, self._hw_mid, self._hw_low,
                               self._hw_win_rate)

        # 2. Simulation result entries
        for title, hi, mid, low, wr in self._sim_entries:
            self._render_entry(title, hi, mid, low, wr)

        # Push entries to top so they don't stretch to fill the scroll area
        self.v.addStretch(1)

    def _render_entry(self, title: str, hi: Tuple[Card, ...], mid: Tuple[Card, ...],
                      low: Tuple[Card, ...], win_rate: float | None):
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

        if win_rate is not None:
            title_text = f"{title} — Win 2 of 3: {win_rate:.2%}" if "Win 2 of 3" not in title else title
        else:
            title_text = title
        title_label = QLabel(title_text)
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
