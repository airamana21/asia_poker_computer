from __future__ import annotations

from typing import Callable, List, Sequence, Tuple

from .cards import Card
from .simulate import simulate_best, SimResult


def evaluate_best_setup(
    hand: Sequence[Card],
    samples: int,
    seed: int | None = None,
    progress: Callable[[float], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> Tuple[SimResult, List[SimResult]]:
    """Public API used by the GUI to compute the best 4‑2‑1 arrangement."""
    return simulate_best(hand, samples=samples, seed=seed, progress=progress, cancel=cancel)
