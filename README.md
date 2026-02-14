# Asia Poker 4-2-1 Monte Carlo Assistant (PySide6)

Cross‑platform Python app to help arrange 7 cards into 4‑card / 2‑card / 1‑card hands for Asia Poker (aka 4‑2‑1). It estimates the best setup by Monte Carlo against a dealer setting by a published House Way.

- GUI: Qt (PySide6), fully resizable — cards and UI elements scale proportionally
- Deck: 53 cards (Joker is Pai Gow style: Ace or to complete straight/flush/straight flush)
- Default samples: 100,000 (configurable via slider)
- Card images: generated locally as PNGs on first run into `assets/cards` and cached

## Quick start

1. Create a virtual environment (recommended) and install deps:

```
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Run the app:

```
python -m src.app
```

Notes for macOS: If Gatekeeper prompts on first launch, allow the Python process to open networkless windows; the app is offline.

## Resizable UI

The window is freely resizable with a **locked aspect ratio** (~2.48:1). Dragging any edge auto‑adjusts the other dimension to keep the ratio. All GUI elements — card buttons, status‑bar slots, result cards, fonts, and spacing — scale proportionally.

Layout: status bar across the top, card grid on the left (65%), controls + results on the right (35%).

- **Aspect ratio lock**: changing width auto‑adjusts height and vice versa
- **Scale factor**: `left_panel_width / grid_natural_width` (grid is 13 × 5 cards at scale 1.0 ≈ 2240 px)
- **Default startup**: 1600 px wide (or OS‑capped), scale ≈ 0.32
- **Min scale**: 0.25 — **Max scale**: 2.0
- **Window size is persisted** in `QSettings` and restored on next launch
- Results panel scrolls vertically if needed; all other content fits without scroll bars

## Performance & parallelism

The Monte Carlo simulator uses **multiprocessing** to distribute samples across
CPU cores and **LRU caches** for hand scoring, yielding ~40–50× end-to-end
speedup over the original single-threaded implementation.

### How it works

| Optimisation | Where | Effect |
|---|---|---|
| `ProcessPoolExecutor` with large per-worker chunks | `src/core/simulate.py` | Scales across CPU cores; each worker warms its own LRU cache |
| `lru_cache` on `score4`, `score2`, `score1` keyed by `frozenset((rank, suit))` | `src/core/ranks.py` | 80–99 % cache hit rate after warmup; avoids redundant scoring |
| Optimised Joker materialisation (targeted suit/rank search) | `src/core/ranks.py` | Reduces Joker evaluations from 56 → ~8–12 per hand |
| Tuple-based score comparison (avoids `Score.__gt__` dispatch) | `src/core/simulate.py` | Faster inner loop comparisons |
| Index-based partition generation | `src/core/partition.py` | Avoids `not in` linear scans |
| `__slots__` on `RankedPartition` | `src/core/partition.py` | Reduces per-object memory and attribute access overhead |

### Tuning knobs

| Env var | Default | Description |
|---|---|---|
| `ASIA_POKER_WORKERS` | `min(cpu_count, 8)` | Number of worker processes. Set to `1` to disable multiprocessing. |

Example (limit to 4 workers):
```
ASIA_POKER_WORKERS=4 python -m src.app        # macOS / Linux
$env:ASIA_POKER_WORKERS=4; python -m src.app   # Windows PowerShell
```

### Benchmarks (6-core machine, 10 000 samples)

| Configuration | Time |
|---|---|
| Original (single-thread, no caching) | ~120 s |
| Single-process + caching + optimisations | ~7 s |
| 6-worker multiprocessing + caching | **~2.5 s** |

## Project layout
See [plans/architecture.md](plans/architecture.md) and rules in [docs/rules.md](docs/rules.md).

## Packaging (optional)
Later we can add PyInstaller specs for one‑click builds on Windows/macOS.
