from __future__ import annotations

"""
Dealer House Way engine.

Note: Exact House Way varies slightly by jurisdiction. This implementation uses a
simple, citation‑aligned deterministic policy: choose the non‑foul 4‑2‑1
partition that maximizes (4‑card score, then 2‑card score, then 1‑card score).

The rules documents referenced in docs/sources.md indicate that for Asia Poker,
casinos prioritize the highest 4‑card hand while keeping 2‑ and 1‑card hands in
order; ties push. This policy is consistent with publicly posted rack cards and
suitable for simulation when the exact internal table "computer" is not
accessible.

If you need a venue‑exact House Way, replace the selector below with a direct
translation of that venue's decision tree, while preserving the same Score and
Partition interfaces.
"""

from typing import Sequence, Tuple

from .cards import Card
from .partition import all_ranked_non_foul, RankedPartition


def set_dealer_421(cards: Sequence[Card]) -> RankedPartition:
    """Deterministic House Way: pick best non‑foul lexicographically.

    Returns a RankedPartition (includes cached scores) for downstream compare.
    """
    cand = all_ranked_non_foul(cards)
    if not cand:
        # Foul all partitions shouldn't happen; fall back to arbitrary first
        from .partition import RankedPartition as RP, generate_partitions
        return RP(generate_partitions(cards)[0])
    return max(cand, key=lambda rp: rp.key_house())
