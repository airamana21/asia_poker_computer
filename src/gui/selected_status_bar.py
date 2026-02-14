from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from ..core.cards import Card, JOKER
from .assets import asset_path, CARD_W, CARD_H


class ClickableLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event):  # type: ignore[override]
        self.clicked.emit()
        return super().mouseReleaseEvent(event)


class SelectedStatusBar(QFrame):
    def __init__(self, on_slot_clicked: Callable[[int], None]):
        super().__init__()
        self.on_slot_clicked = on_slot_clicked
        self.setObjectName("SelectedStatusBar")
        self.setFrameShape(QFrame.Shape.Box)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)
        self._layout = layout
        self._base_margins = layout.contentsMargins()
        self._base_spacing = layout.spacing()
        self._scale = 0.0  # force first set_scale to apply
        self._cards: List[Optional[Card]] = [None] * 7
        self.slots: List[ClickableLabel] = []
        for i in range(7):
            lbl = ClickableLabel()
            lbl.setStyleSheet("background: #eee; border: 1px dashed #999;")
            lbl.setScaledContents(True)
            lbl.clicked.connect(lambda i=i: self.on_slot_clicked(i))
            layout.addWidget(lbl)
            self.slots.append(lbl)
        self.set_scale(1.0)

    def set_cards(self, cards: List[Optional[Card]]):
        for idx in range(7):
            self._cards[idx] = cards[idx] if idx < len(cards) else None
        self._refresh_pixmaps()

    def set_scale(self, scale: float):
        if abs(scale - self._scale) < 1e-3:
            return
        self._scale = scale
        margins = self._base_margins
        self._layout.setContentsMargins(
            int(margins.left() * scale),
            int(margins.top() * scale),
            int(margins.right() * scale),
            int(margins.bottom() * scale),
        )
        self._layout.setSpacing(int(self._base_spacing * scale))
        slot_size = QSize(int(CARD_W * 0.9 * scale), int(CARD_H * 0.9 * scale))
        for lbl in self.slots:
            lbl.setFixedSize(slot_size)
        self._refresh_pixmaps()

    def _refresh_pixmaps(self):
        for lbl, card in zip(self.slots, self._cards):
            if card is None:
                lbl.clear()
                lbl.setToolTip("")
            else:
                pix = QPixmap(asset_path(card))
                lbl.setPixmap(
                    pix.scaled(
                        lbl.width(),
                        lbl.height(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                lbl.setToolTip(card.id())
