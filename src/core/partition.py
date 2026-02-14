from __future__ import annotations

from itertools import combinations
from typing import Iterable, List, Sequence, Tuple

from .cards import Card
from .ranks import score1, score2, score4, compare_scores, Score

Partition = Tuple[Tuple[Card, ...], Tuple[Card, ...], Tuple[Card, ...]]  # (4,2,1)


def generate_partitions(cards: Sequence[Card]) -> List[Partition]:
    """Generate all C(7,4)*C(3,2) = 105 partitions of 7 cards into (4,2,1).

    Uses index-based selection to avoid linear-scan `not in` checks.
    """
    assert len(cards) == 7
    cards_list = list(cards)
    indices = range(7)
    parts: List[Partition] = []
    for hi_idx in combinations(indices, 4):
        hi = tuple(cards_list[i] for i in hi_idx)
        rem_idx = [i for i in indices if i not in hi_idx]
        r0, r1, r2 = rem_idx
        # C(3,2) = 3 mid combos, each leaves 1 low card
        parts.append((hi, (cards_list[r0], cards_list[r1]), (cards_list[r2],)))
        parts.append((hi, (cards_list[r0], cards_list[r2]), (cards_list[r1],)))
        parts.append((hi, (cards_list[r1], cards_list[r2]), (cards_list[r0],)))
    return parts


class RankedPartition:
    __slots__ = ('hi', 'mid', 'low', 's4', 's2', 's1')

    def __init__(self, part: Partition):
        self.hi, self.mid, self.low = part
        self.s4: Score = score4(self.hi)
        self.s2: Score = score2(self.mid)
        self.s1: Score = score1(self.low)

    def foul(self) -> bool:
        # Must be s4 >= s2 >= s1 in poker ordering
        return self.s4.tuple() < self.s2.tuple() or self.s2.tuple() < self.s1.tuple()

    def key_house(self):
        # Deterministic ordering approximating typical House Way preferences
        return (self.s4.tuple(), self.s2.tuple(), self.s1.tuple())


def all_ranked_non_foul(cards: Sequence[Card]) -> List[RankedPartition]:
    res: List[RankedPartition] = []
    for p in generate_partitions(cards):
        rp = RankedPartition(p)
        if not rp.foul():
            res.append(rp)
    return res
