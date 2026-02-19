from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from PySide6.QtCore import QSize, Qt, QEvent
from PySide6.QtGui import QIcon, QColor
from PySide6.QtWidgets import (QFrame, QGridLayout, QPushButton, QSizePolicy,
                               QWidget, QGraphicsDropShadowEffect)

from ..core.cards import Card, SUITS, RANKS, JOKER
from .assets import asset_path, CARD_W, CARD_H

# Number of columns (ranks) and rows (suits + joker)
_COLS = len(RANKS)   # 13
_ROWS = len(SUITS) + 1  # 5 (4 suits + joker row)

# Layout constants at scale=1.0
_BTN_RATIO = 1.05
_ICON_RATIO = 0.95
_JOKER_BTN_RATIO = 0.9
_JOKER_ICON_RATIO = 0.75
_GRID_SPACING = 4
_GRID_MARGIN = 4
_HOVER_SCALE = 1.07  # 7% scale-up on hover


def grid_natural_size() -> Tuple[int, int]:
    """Return (width, height) of the card grid at scale = 1.0."""
    btn_w = int(CARD_W * _BTN_RATIO)
    btn_h = int(CARD_H * _BTN_RATIO)
    # Joker row is one button spanning all columns, height driven by joker ratio
    joker_h = int(CARD_H * _JOKER_BTN_RATIO)
    w = _COLS * btn_w + (_COLS - 1) * _GRID_SPACING + 2 * _GRID_MARGIN
    h = (len(SUITS) * btn_h + joker_h
         + _ROWS * _GRID_SPACING   # spacing between rows (approx)
         + 2 * _GRID_MARGIN)
    return w, h


class CardSelector(QFrame):
    def __init__(self, on_card_clicked: Callable[[Card], None]):
        super().__init__()
        self.on_card_clicked = on_card_clicked
        self.setObjectName("CardSelector")
        layout = QGridLayout(self)
        layout.setContentsMargins(_GRID_MARGIN, _GRID_MARGIN,
                                  _GRID_MARGIN, _GRID_MARGIN)
        layout.setSpacing(_GRID_SPACING)
        self.buttons: Dict[str, QPushButton] = {}
        self._scale = 0.0  # force first set_scale to apply
        self._joker_id: str | None = None

        # Grid by suit rows, rank columns, plus a Joker button at the end
        for row, suit in enumerate(SUITS):
            for col, rank in enumerate(RANKS):
                card = Card(rank, suit)
                btn = QPushButton()
                btn.setIcon(QIcon(asset_path(card)))
                btn.setSizePolicy(QSizePolicy.Policy.Fixed,
                                  QSizePolicy.Policy.Fixed)
                btn.clicked.connect(
                    lambda _=False, c=card: self.on_card_clicked(c))
                btn.setToolTip(card.id())
                btn.setAttribute(Qt.WidgetAttribute.WA_Hover)  # Enable hover events
                btn.installEventFilter(self)  # Install event filter for hover effects
                layout.addWidget(btn, row, col)
                self.buttons[card.id()] = btn
        # Joker button
        j = Card(JOKER, None)
        jbtn = QPushButton()
        jbtn.setIcon(QIcon(asset_path(j)))
        jbtn.setSizePolicy(QSizePolicy.Policy.Fixed,
                           QSizePolicy.Policy.Fixed)
        jbtn.clicked.connect(lambda _=False, c=j: self.on_card_clicked(c))
        jbtn.setToolTip(j.id())
        jbtn.setAttribute(Qt.WidgetAttribute.WA_Hover)  # Enable hover events
        jbtn.installEventFilter(self)  # Install event filter for hover effects
        layout.addWidget(jbtn, len(SUITS), 0, 1, _COLS)
        self.buttons[j.id()] = jbtn
        self._joker_id = j.id()

        # Apply initial scale
        self.set_scale(1.0)

    def _apply_sizes(self, btn: QPushButton, icon_ratio: float,
                     button_ratio: float, card_id: str):
        """Apply sizes to button."""
        iw = int(CARD_W * icon_ratio * self._scale)
        ih = int(CARD_H * icon_ratio * self._scale)
        bw = int(CARD_W * button_ratio * self._scale)
        bh = int(CARD_H * button_ratio * self._scale)
        btn.setIconSize(QSize(max(1, iw), max(1, ih)))
        btn.setFixedSize(QSize(max(1, bw), max(1, bh)))

    def set_scale(self, scale: float):
        if abs(scale - self._scale) < 1e-3:
            return
        # Clean up any active hover before changing scale
        for btn in self.buttons.values():
            self._remove_hover(btn)
        self._scale = scale
        # Update layout spacing/margins proportionally
        lay = self.layout()
        if lay:
            lay.setSpacing(max(1, int(_GRID_SPACING * scale)))
            m = max(1, int(_GRID_MARGIN * scale))
            lay.setContentsMargins(m, m, m, m)
        for card_id, btn in self.buttons.items():
            if card_id == self._joker_id:
                self._apply_sizes(btn, _JOKER_ICON_RATIO, _JOKER_BTN_RATIO, card_id)
            else:
                self._apply_sizes(btn, _ICON_RATIO, _BTN_RATIO, card_id)
        self.updateGeometry()

    # ── Hover helpers ──────────────────────────────────────

    def _apply_hover(self, btn: QPushButton):
        """Apply scale-up + glow to a card button without affecting layout."""
        layout = self.layout()

        # Save original state
        btn._hover_orig_geom = btn.geometry()
        btn._hover_orig_icon = btn.iconSize()

        # Freeze layout so other cards stay put
        layout.setEnabled(False)

        # Bring this card on top of its neighbours
        btn.raise_()

        # Compute scaled geometry centred on the original centre
        og = btn._hover_orig_geom
        nw = int(og.width() * _HOVER_SCALE)
        nh = int(og.height() * _HOVER_SCALE)
        cx, cy = og.center().x(), og.center().y()

        # Relax the fixed-size constraints so the widget can grow
        btn.setMinimumSize(0, 0)
        btn.setMaximumSize(16777215, 16777215)
        btn.setGeometry(cx - nw // 2, cy - nh // 2, nw, nh)

        # Scale icon proportionally
        oiw = btn._hover_orig_icon.width()
        oih = btn._hover_orig_icon.height()
        btn.setIconSize(QSize(int(oiw * _HOVER_SCALE),
                              int(oih * _HOVER_SCALE)))

        # Blue glow
        shadow = QGraphicsDropShadowEffect(btn)
        shadow.setBlurRadius(35)
        shadow.setColor(QColor(61, 174, 233, 255))
        shadow.setOffset(0, 0)
        btn.setGraphicsEffect(shadow)

    def _remove_hover(self, btn: QPushButton):
        """Restore a button to its normal size and re-enable layout."""
        if not hasattr(btn, '_hover_orig_geom'):
            btn.setGraphicsEffect(None)
            return

        og = btn._hover_orig_geom
        oi = btn._hover_orig_icon

        # Restore original fixed size, position, icon
        btn.setFixedSize(og.size())
        btn.setGeometry(og)
        btn.setIconSize(oi)
        btn.setGraphicsEffect(None)

        del btn._hover_orig_geom
        del btn._hover_orig_icon

        # Re-enable layout
        self.layout().setEnabled(True)

    def eventFilter(self, obj, event):
        """Handle hover events for card buttons."""
        if isinstance(obj, QPushButton) and obj in self.buttons.values():
            # Skip hover effects for disabled buttons
            if not obj.isEnabled():
                return super().eventFilter(obj, event)

            if event.type() == QEvent.Type.Enter:
                self._apply_hover(obj)

            elif event.type() == QEvent.Type.Leave:
                self._remove_hover(obj)

        return super().eventFilter(obj, event)

    def set_disabled(self, ids: List[str]):
        for k, b in self.buttons.items():
            disabled = k in ids
            if disabled:
                self._remove_hover(b)
            b.setEnabled(not disabled)
