from __future__ import annotations

from typing import List, Sequence

from PySide6.QtCore import QObject, QThread, Signal

from ..core.cards import Card
from ..core.evaluator import evaluate_best_setup


class SimWorker(QObject):
    progress = Signal(float)
    finished = Signal(object, object)  # best, all_results
    error = Signal(str)
    canceled = Signal()

    def __init__(self, hand: Sequence[Card], samples: int):
        super().__init__()
        self.hand = list(hand)
        self.samples = int(samples)
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            best, all_results = evaluate_best_setup(
                self.hand,
                samples=self.samples,
                progress=self.progress.emit,
                cancel=lambda: self._cancel,
            )
            if self._cancel:
                self.canceled.emit()
                return
            self.finished.emit(best, all_results)
        except Exception as e:
            self.error.emit(str(e))
