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
See [`plans/architecture.md`](plans/architecture.md) and rules in [`docs/rules.md`](docs/rules.md).

## Building Standalone Executables

Create one-click distributable executables for Windows and macOS using PyInstaller. The build scripts automatically handle dependency installation, asset generation, and packaging.

### Windows Build

**Requirements**: Python 3.8+ installed and in PATH

**One-click build**:
```powershell
.\build_windows.ps1
```

This script will:
1. Create/activate a virtual environment
2. Install dependencies + PyInstaller
3. Generate card assets
4. Build the executable with PyInstaller
5. Output to `dist/AsiaPoker421/AsiaPoker421.exe`

**Manual build** (if needed):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pyinstaller
python -c "from src.gui.assets import ensure_assets; ensure_assets()"
pyinstaller --clean --noconfirm build_windows.spec
```

**Distribution**: ZIP the entire `dist/AsiaPoker421` folder. Users extract and run `AsiaPoker421.exe`.

### macOS Build

**Requirements**: Python 3.8+ (typically `python3`)

**One-click build**:
```bash
chmod +x build_macos.sh  # First time only
./build_macos.sh
```

This script will:
1. Create/activate a virtual environment
2. Install dependencies + PyInstaller
3. Generate card assets
4. Build the app bundle with PyInstaller
5. Output to `dist/AsiaPoker421.app`

**Manual build** (if needed):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller
python -c "from src.gui.assets import ensure_assets; ensure_assets()"
pyinstaller --clean --noconfirm build_macos.spec
```

**Distribution**: Create a DMG or ZIP the `.app` bundle.

**Gatekeeper Note**: Unsigned apps show a security warning on first launch. Users should right-click → Open (not double-click) the first time to bypass Gatekeeper.

### Build Output Sizes

| Platform | Uncompressed | Compressed (ZIP) |
|----------|--------------|------------------|
| Windows  | ~80-105 MB   | ~30-40 MB        |
| macOS    | ~90-115 MB   | ~35-45 MB        |

Sizes include Qt6 framework, PySide6, NumPy, and bundled card assets.

### Technical Details

The packaging solution addresses several challenges:

1. **Resource Paths**: [`src/utils/resources.py`](src/utils/resources.py) detects PyInstaller's frozen mode and resolves bundled files correctly
2. **Multiprocessing**: [`multiprocessing.freeze_support()`](src/app.py:13) enables parallel simulation in frozen executables
3. **Writable Assets**: In frozen mode, card assets are copied to user data directories:
   - Windows: `%LOCALAPPDATA%/AsiaPoker421/assets/cards`
   - macOS: `~/Library/Application Support/AsiaPoker421/assets/cards`
4. **QSS Stylesheet**: Bundled and loaded via resource path helper

See [`plans/packaging.md`](plans/packaging.md) for complete implementation details.

### Distribution Best Practices

**For Windows users**:
1. Extract the ZIP archive
2. Run `AsiaPoker421.exe`
3. Windows Defender may scan the executable on first run (normal behavior)
4. Card images generate automatically on first launch if needed

**For macOS users**:
1. Extract/mount the archive
2. Move `AsiaPoker421.app` to Applications folder (optional)
3. **First launch only**: Right-click → Open (bypasses Gatekeeper)
4. Subsequent launches: Double-click normally

### Known Issues

| Issue | Workaround |
|-------|------------|
| Antivirus false positive (Windows) | Expected for unsigned PyInstaller executables; source code available for verification |
| macOS Gatekeeper warning | Right-click → Open on first launch; consider code signing for professional distribution |
| Large download size | Qt6 framework is bundled; size is normal for PySide6 applications |
| Slow first launch | PyInstaller extracts to temp directory; subsequent launches are faster |

### Future Enhancements

- Code signing (Windows Authenticode, macOS Developer ID)
- macOS notarization for seamless Gatekeeper approval
- Custom installers (WiX Toolset for Windows, DMG with background for macOS)
- CI/CD automation with GitHub Actions
- Linux support (AppImage or Flatpak)
