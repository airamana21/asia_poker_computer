from __future__ import annotations

from typing import Callable, List, Sequence, Tuple

from .cards import Card
from .simulate import simulate_best, SimResult
from .house_way import set_dealer_421
from .partition import RankedPartition


def evaluate_best_setup(
    hand: Sequence[Card],
    samples: int,
    seed: int | None = None,
    progress: Callable[[float], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> Tuple[SimResult, List[SimResult]]:
    """Public API used by the GUI to compute the best 4‑2‑1 arrangement."""
    return simulate_best(hand, samples=samples, seed=seed, progress=progress, cancel=cancel)


def house_way_result(hand: Sequence[Card]) -> RankedPartition:
    """Compute the dealer's House Way arrangement for the given 7 cards.
    
    This is deterministic and instant (no simulation).
    Returns a RankedPartition with the 4-card, 2-card, and 1-card hands.
    """
    return set_dealer_421(hand)
