from __future__ import annotations

import os
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable, List, Sequence, Tuple

import numpy as np

from .cards import Card, remaining_deck
from .partition import RankedPartition, all_ranked_non_foul
from .house_way import set_dealer_421
from .ranks import Score, score_to_int

# ── Configuration ─────────────────────────────────────────────
# Number of worker processes.  Override with ASIA_POKER_WORKERS env var.
# Default: min(cpu_count, 8).  Set to 1 to disable multiprocessing.
_MAX_WORKERS = min(os.cpu_count() or 4, 8)
_WORKERS = int(os.environ.get("ASIA_POKER_WORKERS", _MAX_WORKERS))

# Minimum samples before we bother spawning subprocesses
_MP_THRESHOLD = 2000

# Set ASIA_POKER_NO_NUMPY=1 to fall back to pure-Python loops (debug only)
_USE_NUMPY = not bool(int(os.environ.get("ASIA_POKER_NO_NUMPY", "0")))


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
    player_ints_flat: List[List[int]],   # shape (P, 3) as nested list
    chunk_size: int,
    seed: int,
) -> Tuple[List[int], List[int], List[int]]:
    """Run *chunk_size* Monte Carlo samples in this worker process.

    Uses batched NumPy vectorized comparison of all player partitions
    against batches of dealer hands.  Arguments use plain Python types
    for pickling on Windows (spawn).

    Returns (W, L, P) lists of length P.
    """
    import numpy as _np
    from .cards import Card as C
    from .house_way import set_dealer_421 as _dealer_421
    from .ranks import score_to_int as _s2i

    _B = 500  # batch size

    rng = random.Random(seed)
    pi = _np.array(player_ints_flat, dtype=_np.int64)  # (P, 3)
    p4, p2, p1 = pi[:, 0], pi[:, 1], pi[:, 2]         # each (P,)
    n_parts = pi.shape[0]

    W = _np.zeros(n_parts, dtype=_np.int64)
    L = _np.zeros(n_parts, dtype=_np.int64)
    P = _np.zeros(n_parts, dtype=_np.int64)

    deck = [C(rank, suit) for rank, suit in deck_cards]

    d4_buf = _np.empty(_B, dtype=_np.int64)
    d2_buf = _np.empty(_B, dtype=_np.int64)
    d1_buf = _np.empty(_B, dtype=_np.int64)

    for batch_start in range(0, chunk_size, _B):
        B = min(_B, chunk_size - batch_start)

        for j in range(B):
            dealer7 = rng.sample(deck, 7)
            dealer = _dealer_421(dealer7)
            d4_buf[j] = _s2i(dealer.s4)
            d2_buf[j] = _s2i(dealer.s2)
            d1_buf[j] = _s2i(dealer.s1)

        d4 = d4_buf[:B]
        d2 = d2_buf[:B]
        d1 = d1_buf[:B]

        w4 = p4[:, None] > d4[None, :]
        w2 = p2[:, None] > d2[None, :]
        w1 = p1[:, None] > d1[None, :]

        l4 = p4[:, None] < d4[None, :]
        l2 = p2[:, None] < d2[None, :]
        l1 = p1[:, None] < d1[None, :]

        sub_wins = w4.view(_np.uint8) + w2.view(_np.uint8) + w1.view(_np.uint8)
        sub_losses = l4.view(_np.uint8) + l2.view(_np.uint8) + l1.view(_np.uint8)

        w_flag = sub_wins >= 2
        l_flag = sub_losses >= 2

        W += w_flag.sum(axis=1)
        L += l_flag.sum(axis=1)
        P += (~(w_flag | l_flag)).sum(axis=1)

    return W.tolist(), L.tolist(), P.tolist()


def _sim_chunk_pure(
    deck_cards: List[Tuple[str, str | None]],
    part_score_tuples: List[Tuple[
        Tuple[int, Tuple[int, ...]],
        Tuple[int, Tuple[int, ...]],
        Tuple[int, Tuple[int, ...]],
    ]],
    chunk_size: int,
    seed: int,
) -> Tuple[List[int], List[int], List[int]]:
    """Pure-Python fallback for _sim_chunk (no NumPy)."""
    from .cards import Card as C
    from .house_way import set_dealer_421 as _dealer_421

    rng = random.Random(seed)
    n_parts = len(part_score_tuples)

    W = [0] * n_parts
    L = [0] * n_parts
    P = [0] * n_parts

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
    Inner partition comparison is vectorized via NumPy int64 encoding
    unless ASIA_POKER_NO_NUMPY=1 is set.

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
        if _USE_NUMPY:
            return _simulate_single_numpy(parts, deck, n, rng, progress, cancel)
        return _simulate_single_pure(parts, deck, n, rng, progress, cancel)

    # ── Multi-process path ────────────────────────────────────
    deck_cards = [(c.rank, c.suit) for c in deck]

    # Choose chunk function and data format based on numpy availability
    if _USE_NUMPY:
        player_ints_flat = [
            [score_to_int(rp.s4), score_to_int(rp.s2), score_to_int(rp.s1)]
            for rp in parts
        ]
        chunk_fn = _sim_chunk
    else:
        part_score_tuples = [
            (rp.s4.tuple(), rp.s2.tuple(), rp.s1.tuple())
            for rp in parts
        ]
        chunk_fn = _sim_chunk_pure

    # Give each worker one large chunk (= samples / workers)
    workers = min(_WORKERS, max(1, n // _MP_THRESHOLD))
    base = n // workers
    remainder = n % workers

    chunks: List[Tuple[int, int]] = []
    for w in range(workers):
        cs = base + (1 if w < remainder else 0)
        chunks.append((cs, rng.randint(0, 2**63)))

    W = [0] * num_parts
    L = [0] * num_parts
    P = [0] * num_parts
    completed_samples = 0

    try:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for cs, s in chunks:
                payload = player_ints_flat if _USE_NUMPY else part_score_tuples
                fut = executor.submit(chunk_fn, deck_cards, payload, cs, s)
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
        if _USE_NUMPY:
            return _simulate_single_numpy(parts, deck, n, rng, progress, cancel)
        return _simulate_single_pure(parts, deck, n, rng, progress, cancel)

    results: List[SimResult] = [
        SimResult(rp=parts[i], wins=W[i], losses=L[i], pushes=P[i])
        for i in range(num_parts)
    ]
    results.sort(key=lambda r: (r.win_rate, r.wins), reverse=True)
    best = results[0]
    if progress:
        progress(1.0)
    return best, results


# Batch size for vectorized comparison — accumulate this many dealer hands
# before comparing against all player partitions in one NumPy operation.
_BATCH = 500


def _simulate_single_numpy(
    parts: List[RankedPartition],
    deck: List[Card],
    n: int,
    rng: random.Random,
    progress: Callable[[float], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> Tuple[SimResult, List[SimResult]]:
    """NumPy-vectorized single-process simulation loop.

    Dealer hands are scored in Python (house-way logic is branchy), but the
    comparison of all P player partitions against a *batch* of B dealer hands
    is done in one vectorized operation: (P, 1) vs (1, B) broadcast per
    sub-hand, giving a real speedup over the pure-Python inner loop.
    """
    num_parts = len(parts)

    # Pre-compute player score int64 columns — contiguous (P,) each
    p4 = np.array([score_to_int(rp.s4) for rp in parts], dtype=np.int64)
    p2 = np.array([score_to_int(rp.s2) for rp in parts], dtype=np.int64)
    p1 = np.array([score_to_int(rp.s1) for rp in parts], dtype=np.int64)

    W = np.zeros(num_parts, dtype=np.int64)
    L = np.zeros(num_parts, dtype=np.int64)
    P = np.zeros(num_parts, dtype=np.int64)

    completed = 0
    cancelled = False

    # Pre-allocate dealer batch buffer
    d4_buf = np.empty(_BATCH, dtype=np.int64)
    d2_buf = np.empty(_BATCH, dtype=np.int64)
    d1_buf = np.empty(_BATCH, dtype=np.int64)

    for batch_start in range(0, n, _BATCH):
        if cancelled:
            break
        B = min(_BATCH, n - batch_start)

        # Fill dealer batch (Python loop — house-way is branchy)
        for j in range(B):
            if cancel and cancel():
                cancelled = True
                B = j  # only use hands scored so far
                break
            dealer7 = rng.sample(deck, 7)
            dealer = set_dealer_421(dealer7)
            d4_buf[j] = score_to_int(dealer.s4)
            d2_buf[j] = score_to_int(dealer.s2)
            d1_buf[j] = score_to_int(dealer.s1)

        if B == 0:
            break

        # Slices for this batch
        d4 = d4_buf[:B]
        d2 = d2_buf[:B]
        d1 = d1_buf[:B]

        # Vectorized comparison: (P, 1) vs (1, B) -> (P, B) per sub-hand
        w4 = p4[:, None] > d4[None, :]  # (P, B) bool
        w2 = p2[:, None] > d2[None, :]
        w1 = p1[:, None] > d1[None, :]

        l4 = p4[:, None] < d4[None, :]
        l2 = p2[:, None] < d2[None, :]
        l1 = p1[:, None] < d1[None, :]

        sub_wins = w4.view(np.uint8) + w2.view(np.uint8) + w1.view(np.uint8)    # (P, B)
        sub_losses = l4.view(np.uint8) + l2.view(np.uint8) + l1.view(np.uint8)  # (P, B)

        w_flag = sub_wins >= 2  # (P, B)
        l_flag = sub_losses >= 2

        W += w_flag.sum(axis=1)
        L += l_flag.sum(axis=1)
        P += (~(w_flag | l_flag)).sum(axis=1)

        completed += B
        if progress:
            progress(completed / n)

    results: List[SimResult] = [
        SimResult(rp=parts[i], wins=int(W[i]), losses=int(L[i]), pushes=int(P[i]))
        for i in range(num_parts)
    ]
    results.sort(key=lambda r: (r.win_rate, r.wins), reverse=True)
    best = results[0]
    if progress:
        progress(1.0)
    return best, results


def _simulate_single_pure(
    parts: List[RankedPartition],
    deck: List[Card],
    n: int,
    rng: random.Random,
    progress: Callable[[float], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> Tuple[SimResult, List[SimResult]]:
    """Pure-Python single-process simulation loop (fallback)."""
    num_parts = len(parts)
    W = [0] * num_parts
    L = [0] * num_parts
    P = [0] * num_parts

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
