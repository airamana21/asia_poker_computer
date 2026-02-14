from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, List, Sequence, Tuple

from .cards import Card, JOKER, RANK_TO_VAL, RANKS

# Categories ordered high to low
CAT_SF = 7
CAT_FOUR = 6
CAT_FLUSH = 5
CAT_STRAIGHT = 4
CAT_TRIPS = 3
CAT_TWO_PAIR = 2
CAT_PAIR = 1
CAT_HIGH = 0


@dataclass(frozen=True)
class Score:
    cat: int
    keys: Tuple[int, ...]  # tie breakers high to low (numeric ranks 2..14)

    def tuple(self) -> Tuple[int, Tuple[int, ...]]:
        return (self.cat, self.keys)

    def __lt__(self, other: "Score") -> bool:  # type: ignore[override]
        return self.tuple() < other.tuple()

    def __gt__(self, other: "Score") -> bool:  # type: ignore[override]
        return self.tuple() > other.tuple()


# Helpers
STRAIGHTS = [
    (14, 5, 4, 3),  # A234 (A low)
    (14, 13, 12, 11),
    (13, 12, 11, 10),
    (12, 11, 10, 9),
    (11, 10, 9, 8),
    (10, 9, 8, 7),
    (9, 8, 7, 6),
    (8, 7, 6, 5),
    (7, 6, 5, 4),
    (6, 5, 4, 3),
    (5, 4, 3, 2),
]

# Pre-compute frozensets for fast subset checks
_STRAIGHT_SETS = [(frozenset(w), w) for w in STRAIGHTS]


def _is_straight(vals: List[int]) -> Tuple[bool, Tuple[int, ...]]:
    s = frozenset(vals)
    if len(s) < 4:
        return False, ()
    for fset, window in _STRAIGHT_SETS:
        if fset <= s:
            return True, window
    return False, ()


# ── Raw scoring functions (operate on value/suit tuples for speed) ────

def _eval4_raw(vals: Tuple[int, ...], suits: Tuple[str, ...]) -> Tuple[int, Tuple[int, ...]]:
    """Score a 4-card hand from raw vals and suits. Returns (cat, keys) tuple."""
    flush = (suits[0] == suits[1] == suits[2] == suits[3])
    
    vals_list = list(vals)
    is_straight, seq = _is_straight(vals_list)

    if flush and is_straight:
        return (CAT_SF, seq)

    cnt = Counter(vals)
    most = cnt.most_common(2)
    if most[0][1] == 4:
        return (CAT_FOUR, (most[0][0],))

    if flush:
        return (CAT_FLUSH, tuple(sorted(vals, reverse=True)))

    if is_straight:
        return (CAT_STRAIGHT, seq)

    if most[0][1] == 3:
        trip = most[0][0]
        kicker = max(v for v in vals if v != trip)
        return (CAT_TRIPS, (trip, kicker))

    if most[0][1] == 2 and len(most) > 1 and most[1][1] == 2:
        pair_hi = max(most[0][0], most[1][0])
        pair_lo = min(most[0][0], most[1][0])
        return (CAT_TWO_PAIR, (pair_hi, pair_lo))

    if most[0][1] == 2:
        pair = most[0][0]
        kickers = sorted((v for v in vals if v != pair), reverse=True)
        return (CAT_PAIR, (pair, *kickers))

    return (CAT_HIGH, tuple(sorted(vals, reverse=True)))


def _eval4_no_joker(cards: Sequence[Card]) -> Score:
    vals = tuple(c.val for c in cards)
    suits = tuple(c.suit for c in cards)
    cat, keys = _eval4_raw(vals, suits)
    return Score(cat, keys)


def _materialize_with_joker(cards: Sequence[Card]) -> List[Tuple[Score, bool]]:
    """Generate candidate scores replacing the Joker as allowed.

    Optimized: instead of trying all 52 rank+suit combos, we target only
    suits/ranks that could form a flush or straight, drastically reducing
    evaluations.
    """
    from .cards import SUITS, Card as C

    non_j = [c for c in cards if c.rank != JOKER]
    non_j_vals = [c.val for c in non_j]
    non_j_suits = [c.suit for c in non_j]
    results: List[Tuple[Score, bool]] = []

    suit_counts = Counter(non_j_suits)

    # ── Flush candidates: only try the suit that has 3 cards (needs 1 more) ──
    flush_suits = [s for s, cnt in suit_counts.items() if cnt >= 3]

    for suit in flush_suits:
        for val in range(2, 15):
            repl = C(RANKS[val - 2], suit)
            sc = _eval4_no_joker([*non_j, repl])
            if sc.cat in (CAT_SF, CAT_FLUSH):
                results.append((sc, True))

    # ── Straight candidates: try ranks that could complete a straight ──
    val_set = set(non_j_vals)
    straight_ranks: set[int] = set()
    for fset, window in _STRAIGHT_SETS:
        present = sum(1 for v in window if v in val_set)
        if present >= 3:
            for v in window:
                if v not in val_set:
                    straight_ranks.add(v)

    for val in straight_ranks:
        for suit in SUITS:
            repl = C(RANKS[val - 2], suit)
            sc = _eval4_no_joker([*non_j, repl])
            if sc.cat == CAT_STRAIGHT:
                results.append((sc, True))
                break

    # ── Joker as Ace (default, any suit) ──
    for suit in SUITS:
        sc = _eval4_no_joker([*non_j, C("A", suit)])
        results.append((sc, False))

    return results


# ── Cached scoring via frozenset keys ─────────────────────────
# The key is a frozenset of (rank, suit) tuples which is order-independent
# and hashable. Cache sizes are set larger than C(46,4) subsets encountered.

@lru_cache(maxsize=262144)
def _cached_score4(key: frozenset) -> Score:
    """Cached score4 keyed on frozenset of (rank, suit) tuples."""
    cards = [Card(r, s) for r, s in key]
    return _score4_impl(cards)


@lru_cache(maxsize=16384)
def _cached_score2(key: frozenset) -> Score:
    cards = [Card(r, s) for r, s in key]
    return _score2_impl(cards)


@lru_cache(maxsize=4096)
def _cached_score1(rank: str, suit: str | None) -> Score:
    v = 14 if rank == JOKER else RANK_TO_VAL[rank]
    return Score(CAT_HIGH, (v,))


def _score4_impl(cards: Sequence[Card]) -> Score:
    if any(c.rank == JOKER for c in cards):
        cand = _materialize_with_joker(cards)
        best = max(cand, key=lambda t: t[0])
        return best[0]
    else:
        return _eval4_no_joker(cards)


def _score2_impl(cards: Sequence[Card]) -> Score:
    a, b = cards
    vals = sorted([a.val, b.val], reverse=True)
    if a.rank == JOKER or b.rank == JOKER:
        other = b if a.rank == JOKER else a
        if other.val == 14:
            return Score(CAT_PAIR, (14,))
        return Score(CAT_HIGH, (14, other.val))
    if vals[0] == vals[1]:
        return Score(CAT_PAIR, (vals[0],))
    return Score(CAT_HIGH, (vals[0], vals[1]))


def score4(cards: Sequence[Card]) -> Score:
    key = frozenset((c.rank, c.suit) for c in cards)
    return _cached_score4(key)


def score2(cards: Sequence[Card]) -> Score:
    key = frozenset((c.rank, c.suit) for c in cards)
    return _cached_score2(key)


def score1(cards: Sequence[Card]) -> Score:
    c = cards[0]
    return _cached_score1(c.rank, c.suit)


def compare_scores(a: Score, b: Score) -> int:
    """Return 1 if a>b, 0 if equal, -1 if a<b."""
    if a > b:
        return 1
    if a < b:
        return -1
    return 0


def clear_score_caches():
    """Clear all scoring LRU caches (call between simulation runs if needed)."""
    _cached_score4.cache_clear()
    _cached_score2.cache_clear()
    _cached_score1.cache_clear()
