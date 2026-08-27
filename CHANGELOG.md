# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] — 2026-08-28

### Added
- **`elliott_wave_report.py`** — self-contained HTML BUY/SELL Elliott Wave report:
  swing detection, 1-2-3-4-5 / A-B-C labelling, core rule checks (wave 2 holds the
  origin, wave 3 not shortest, wave 4 no overlap), a signal engine that reads the
  currently-forming leg, a Fibonacci buy-zone, and an interactive Plotly chart.
  `TICKER`, `START` and `CURRENCY` are configurable.
- **Fibonacci engine integration** (`fibonacci_calculator.py`): retracements and
  upside **extension targets** (1.272×/1.618×/2.618×) now come from the shared
  calculator instead of hand-rolled arithmetic.
- **scipy `find_peaks` swing detector** as an alternative to the percentage ZigZag,
  selectable via `PIVOT_METHOD` (`'peaks'` default, or `'zigzag'`), with
  `PIVOT_PROMINENCE_PCT` and `PEAK_DISTANCE` knobs. Output matches `zigzag()`'s
  strictly-alternating H/L contract.
- **Frost & Prechter primary-degree "book count"** overlay: identifies the
  whole-series five-wave impulse, labels the decline off the top as wave A and the
  bounce as wave B, projects wave C by Fibonacci multiples of A, and marks the
  50–61.8% impulse-retracement target band. Rendered as a report section, a purple
  A-B-C chart overlay, and a plain-language stance (bull-continuation / wave-B
  bounce / wave-C underway).
- **`example_silver.py`** and **`silver_report.py`** — silver (SI=F) `WaveAnalyzer`
  impulse scan and a report generator that emits both ZigZag and peaks variants
  for comparison.
- **`example_cupid_india.py`** — Cupid Ltd (CUPID.NS) impulse/leading-diagonal scan.
- **`.gitignore`** entries for generated `data/`, `reports/` and `images/`.
- **Documentation:** a "Signal Report" section in `readme.md` and this `CHANGELOG.md`.

### Fixed
- **Zero-range Fibonacci collapse:** when the count anchored on a fresh advance
  (the anchor low was also the most recent pivot), all retracement levels equalled
  the anchor low. The swing high now includes the forming leg, so the buy-zone
  spreads correctly.
- **Wave-C projection breaching the impulse origin:** a shallow wave B produced
  negative/absurd `C = A` targets that would wreck the chart axis. The chart
  projection is clamped to the wave-A retest and origin-breaching targets are
  flagged invalid with an explanatory note.
- **Silent chart-export failure on Timestamp x-values:** kaleido 1.x serialises
  figures with orjson, which cannot encode pandas Timestamps; `_json_safe_dates`
  now coerces wave x-values to native datetimes in `plot_pattern` / `plot_monowave`.

### Changed
- `CURRENCY` is configurable (₹ default; `$` for USD tickers such as silver).
- Report header and disclaimer name whichever swing detector produced the count.
