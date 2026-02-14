from __future__ import annotations

import os
import random
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

from .cards import Card, remaining_deck
from .partition import RankedPartition, all_ranked_non_foul
from .house_way import set_dealer_421
from .ranks import compare_scores, Score

# ── Configuration ─────────────────────────────────────────────
# Number of worker processes.  Override with ASIA_POKER_WORKERS env var.
# Default: min(cpu_count, 8).  Set to 1 to disable multiprocessing.
_MAX_WORKERS = min(os.cpu_count() or 4, 8)
_WORKERS = int(os.environ.get("ASIA_POKER_WORKERS", _MAX_WORKERS))

# Minimum samples before we bother spawning subprocesses
_MP_THRESHOLD = 2000


class SimResult:
    def __init__(self, rp: RankedPartition, wins: int, losses: int, pushes: int):
        self.rp = rp
        self.wins = wins
        self.losses = losses
        self.pushes = pushes

    @property
    def win_rate(self) -> float:
        n = self.wins + self.losses + self.pushes
        return (self.wins / n) if n else 0.0


# ══════════════════════════════════════════════════════════════
#  Top-level worker function (must be picklable for Windows spawn)
# ══════════════════════════════════════════════════════════════

def _sim_chunk(
    deck_cards: List[Tuple[str, str | None]],
    part_score_tuples: List[Tuple[
        Tuple[int, Tuple[int, ...]],
        Tuple[int, Tuple[int, ...]],
        Tuple[int, Tuple[int, ...]],
    ]],
    chunk_size: int,
    seed: int,
) -> Tuple[List[int], List[int], List[int]]:
    """Run *chunk_size* Monte Carlo samples in this worker process.

    Arguments use plain Python types for pickling on Windows (spawn).
    Each worker gets a large chunk so its LRU score caches warm up
    and subsequent evaluations benefit from cache hits.

    Returns (W, L, P) lists of length == len(part_score_tuples).
    """
    from .cards import Card as C
    from .house_way import set_dealer_421 as _dealer_421

    rng = random.Random(seed)
    n_parts = len(part_score_tuples)

    W = [0] * n_parts
    L = [0] * n_parts
    P = [0] * n_parts

    # Rebuild deck as Card objects inside this process (once)
    deck = [C(rank, suit) for rank, suit in deck_cards]

    for _ in range(chunk_size):
        dealer7 = rng.sample(deck, 7)
        dealer = _dealer_421(dealer7)
        ds4 = dealer.s4.tuple()
        ds2 = dealer.s2.tuple()
        ds1 = dealer.s1.tuple()

        for idx in range(n_parts):
            ps4, ps2, ps1 = part_score_tuples[idx]
            ww = 0
            ll = 0
            # Inline comparisons for speed
            if ps4 > ds4:
                ww += 1
            elif ps4 < ds4:
                ll += 1
            if ps2 > ds2:
                ww += 1
            elif ps2 < ds2:
                ll += 1
            if ps1 > ds1:
                ww += 1
            elif ps1 < ds1:
                ll += 1

            if ww >= 2:
                W[idx] += 1
            elif ll >= 2:
                L[idx] += 1
            else:
                P[idx] += 1

    return W, L, P


# ══════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════

def simulate_best(
    player7: Sequence[Card],
    samples: int = 100_000,
    seed: int | None = None,
    progress: Callable[[float], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> Tuple[SimResult, List[SimResult]]:
    """Monte Carlo estimate of the best 4-2-1 against dealer House Way.

    Uses multiprocessing when *samples* >= _MP_THRESHOLD and _WORKERS > 1.
    Each worker gets samples/workers samples (large chunks) so its per-process
    LRU score caches warm up and deliver high hit rates.

    Returns: (best_result, all_results_sorted_desc)
    """
    rng = random.Random(seed)

    # Precompute player's valid partitions and their scores
    parts: List[RankedPartition] = all_ranked_non_foul(player7)
    if not parts:
        raise ValueError("All partitions foul; check input cards")

    deck = remaining_deck(player7, include_joker=True)
    n = samples
    num_parts = len(parts)

    use_mp = _WORKERS > 1 and n >= _MP_THRESHOLD

    if not use_mp:
        return _simulate_single(parts, deck, n, rng, progress, cancel)

    # ── Multi-process path ────────────────────────────────────
    # Serialize to lightweight tuples for pickling
    deck_cards = [(c.rank, c.suit) for c in deck]

    # Pre-compute score tuples (plain tuples, not Score objects)
    part_score_tuples = [
        (rp.s4.tuple(), rp.s2.tuple(), rp.s1.tuple())
        for rp in parts
    ]

    # Give each worker one large chunk (= samples / workers)
    # so per-process LRU caches warm up and stay effective.
    workers = min(_WORKERS, max(1, n // _MP_THRESHOLD))
    base = n // workers
    remainder = n % workers

    chunks: List[Tuple[int, int]] = []  # (chunk_size, seed)
    for w in range(workers):
        cs = base + (1 if w < remainder else 0)
        chunks.append((cs, rng.randint(0, 2**63)))

    # Aggregated counters
    W = [0] * num_parts
    L = [0] * num_parts
    P = [0] * num_parts
    completed_samples = 0

    try:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for cs, s in chunks:
                fut = executor.submit(
                    _sim_chunk,
                    deck_cards, part_score_tuples, cs, s,
                )
                futures[fut] = cs

            for fut in as_completed(futures):
                if cancel and cancel():
                    for f in futures:
                        f.cancel()
                    break

                cw, cl, cp = fut.result()
                cs = futures[fut]
                for idx in range(num_parts):
                    W[idx] += cw[idx]
                    L[idx] += cl[idx]
                    P[idx] += cp[idx]
                completed_samples += cs

                if progress:
                    progress(completed_samples / n)

    except (BrokenPipeError, OSError):
        return _simulate_single(parts, deck, n, rng, progress, cancel)

    results: List[SimResult] = [
        SimResult(rp=parts[i], wins=W[i], losses=L[i], pushes=P[i])
        for i in range(num_parts)
    ]
    results.sort(key=lambda r: (r.win_rate, r.wins), reverse=True)
    best = results[0]
    if progress:
        progress(1.0)
    return best, results


def _simulate_single(
    parts: List[RankedPartition],
    deck: List[Card],
    n: int,
    rng: random.Random,
    progress: Callable[[float], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> Tuple[SimResult, List[SimResult]]:
    """Single-process simulation loop with tuple-based score comparison."""
    num_parts = len(parts)
    W = [0] * num_parts
    L = [0] * num_parts
    P = [0] * num_parts

    # Pre-compute player score tuples for fast comparison
    p_scores = [
        (rp.s4.tuple(), rp.s2.tuple(), rp.s1.tuple())
        for rp in parts
    ]

    report_every = max(1, n // 100)

    for i in range(n):
        if cancel and cancel():
            break
        dealer7 = rng.sample(deck, 7)
        dealer = set_dealer_421(dealer7)
        ds4 = dealer.s4.tuple()
        ds2 = dealer.s2.tuple()
        ds1 = dealer.s1.tuple()

        for idx in range(num_parts):
            ps4, ps2, ps1 = p_scores[idx]
            ww = 0
            ll = 0
            if ps4 > ds4:
                ww += 1
            elif ps4 < ds4:
                ll += 1
            if ps2 > ds2:
                ww += 1
            elif ps2 < ds2:
                ll += 1
            if ps1 > ds1:
                ww += 1
            elif ps1 < ds1:
                ll += 1

            if ww >= 2:
                W[idx] += 1
            elif ll >= 2:
                L[idx] += 1
            else:
                P[idx] += 1

        if progress and (i + 1) % report_every == 0:
            progress((i + 1) / n)

    results: List[SimResult] = [
        SimResult(rp=parts[i], wins=W[i], losses=L[i], pushes=P[i])
        for i in range(num_parts)
    ]
    results.sort(key=lambda r: (r.win_rate, r.wins), reverse=True)
    best = results[0]
    if progress:
        progress(1.0)
    return best, results
