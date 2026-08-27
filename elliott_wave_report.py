"""
Technical Elliott Wave analyzer + BUY/SELL signal HTML report.

The project's WaveAnalyzer brute-forces *micro* impulses from a single bar and is
poor at answering "what wave is the daily chart in now". For a tradable signal we
need the macro swing structure, so this tool:

  1. reduces the daily series to its significant swings with a percentage ZigZag,
  2. anchors the count at the major swing low and labels the legs 1-2-3-4-5 / A-B-C,
  3. validates the core Elliott rules (wave 2 holds the origin, wave 3 not shortest,
     wave 4 does not overlap wave 1),
  4. reads the *current* (forming) leg to pick a signal per Elliott Wave theory:

        forming wave 2 (dip) ....... BUY (before wave 3)
        forming wave 3 (up) ........ BUY / HOLD  (strongest wave)
        forming wave 4 (dip) ....... BUY THE DIP (late)
        forming wave 5 (up) ........ REDUCE / SELL (impulse ending)
        forming wave A (down) ...... SELL / AVOID (correction begun)
        forming wave B (up) ........ SELL into strength
        forming wave C (down) ...... prepare BUY (correction ending)

  5. computes Fibonacci buy-zones, a measured-move target and the invalidation level,
  6. renders a self-contained interactive HTML report.

Run:  python elliott_wave_report.py
Output: reports/<TICKER>_elliott_report.html
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from scipy.signal import find_peaks
from fibonacci_calculator import FibonacciCalculator

# Shared Fibonacci engine: retracements define the buy-zone, extensions the
# upside projections of the advance. Reused (and cached) across report runs.
_FIB = FibonacciCalculator(cache_size=256)

# ----------------------------- configuration ------------------------------- #
TICKER = 'CUPID.NS'
START = '2025-01-01'
CURRENCY = '₹'             # price symbol used in the report (₹ default; '$' for USD tickers)
PIVOT_METHOD = 'peaks'     # swing detector: 'peaks' (scipy.find_peaks) or 'zigzag' (percent reversal)
ZIGZAG_PCT = 0.12          # 'zigzag': swing reversal threshold that defines a pivot
PIVOT_PROMINENCE_PCT = 0.08  # 'peaks': min pivot prominence as a fraction of the median price
PEAK_DISTANCE = 5          # 'peaks': minimum bars between consecutive pivots
RECENT_PIVOTS = 9          # anchor the count within the most recent swings (current advance)


# ----------------------------- data loading -------------------------------- #
def load_data(ticker: str, start: str) -> pd.DataFrame:
    raw = yf.download(ticker, start=start, auto_adjust=False, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(1)
    return pd.DataFrame({
        'Date': pd.to_datetime(raw.index),
        'Open': raw['Open'].to_numpy(float),
        'High': raw['High'].to_numpy(float),
        'Low': raw['Low'].to_numpy(float),
        'Close': raw['Close'].to_numpy(float),
    }).reset_index(drop=True)


# ------------------------------- zigzag ------------------------------------ #
def zigzag(highs: np.ndarray, lows: np.ndarray, pct: float):
    """Return alternating swing pivots [(idx, price, 'H'|'L'), ...]."""
    n = len(highs)
    pivots = []
    trend = 0                       # +1 up, -1 down, 0 undecided
    hi_idx, hi = 0, highs[0]
    lo_idx, lo = 0, lows[0]
    for i in range(1, n):
        if highs[i] > hi:
            hi, hi_idx = highs[i], i
        if lows[i] < lo:
            lo, lo_idx = lows[i], i
        if trend >= 0 and lows[i] <= hi * (1 - pct):
            pivots.append((hi_idx, hi, 'H'))
            trend, lo, lo_idx = -1, lows[i], i
        elif trend <= 0 and highs[i] >= lo * (1 + pct):
            pivots.append((lo_idx, lo, 'L'))
            trend, hi, hi_idx = 1, highs[i], i
    return pivots


# ------------------------- scipy find_peaks pivots ------------------------- #
def scipy_pivots(highs: np.ndarray, lows: np.ndarray, prominence_pct: float, distance: int):
    """Alternative swing detector using scipy.find_peaks (salvaged from the
    algostack RealTimePeakDetector, minus the streaming machinery).

    Peaks on the highs are 'H', valleys on the lows are 'L'. Prominence is set
    as a fraction of the median price so it behaves like a percentage filter and
    stays comparable to ZIGZAG_PCT. The merged peak/valley set is forced to
    strictly alternate H/L — keeping the more extreme pivot when two of the same
    type are adjacent — so the output matches zigzag()'s contract exactly.
    """
    scale = float(np.nanmedian(highs))
    prom = prominence_pct * scale
    peak_idx, _ = find_peaks(highs, prominence=prom, distance=distance)
    valley_idx, _ = find_peaks(-lows, prominence=prom, distance=distance)

    piv = [(int(i), float(highs[i]), 'H') for i in peak_idx]
    piv += [(int(i), float(lows[i]), 'L') for i in valley_idx]
    piv.sort(key=lambda p: p[0])

    merged: list = []
    for p in piv:
        if merged and merged[-1][2] == p[2]:           # same type twice in a row
            prev = merged[-1]
            more_extreme = (p[2] == 'H' and p[1] > prev[1]) or (p[2] == 'L' and p[1] < prev[1])
            if more_extreme:
                merged[-1] = p
        else:
            merged.append(p)
    return merged


def detect_pivots(highs: np.ndarray, lows: np.ndarray):
    """Dispatch to the configured swing detector (see PIVOT_METHOD)."""
    if PIVOT_METHOD == 'peaks':
        return scipy_pivots(highs, lows, PIVOT_PROMINENCE_PCT, PEAK_DISTANCE)
    return zigzag(highs, lows, ZIGZAG_PCT)


# --------------------------- elliott labelling ----------------------------- #
WAVE_SEQUENCE = ['1', '2', '3', '4', '5', 'A', 'B', 'C']


def analyze(df: pd.DataFrame):
    highs, lows, closes = df['High'].to_numpy(), df['Low'].to_numpy(), df['Close'].to_numpy()
    last_idx = len(df) - 1
    last_close = float(closes[-1])

    pivots = detect_pivots(highs, lows)
    if len(pivots) < 2:
        return None

    # Anchor the count on the recent advance: within the last RECENT_PIVOTS swings,
    # start at the lowest swing low. Anchoring at the all-time low is meaningless for a
    # split-adjusted series that spans many multiples (early tiny prices dominate %-swings).
    tail = pivots[max(0, len(pivots) - RECENT_PIVOTS):]
    low_positions = [p for p in range(len(tail)) if tail[p][2] == 'L']
    if not low_positions:
        return None
    origin_pos = min(low_positions, key=lambda p: tail[p][1])
    seq = tail[origin_pos:]
    if seq[0][2] != 'L':
        return None

    # completed legs = consecutive pivot pairs; forming leg runs last pivot -> now
    legs = []
    for a in range(len(seq) - 1):
        (i0, p0, _), (i1, p1, _) = seq[a], seq[a + 1]
        legs.append(dict(label=WAVE_SEQUENCE[a] if a < len(WAVE_SEQUENCE) else '?',
                         i0=i0, i1=i1, p0=p0, p1=p1,
                         up=p1 > p0, forming=False))
    forming_no = len(legs) + 1                      # 1-indexed wave now forming
    last_piv = seq[-1]
    forming_label = WAVE_SEQUENCE[len(legs)] if len(legs) < len(WAVE_SEQUENCE) else '?'
    forming = dict(label=forming_label, i0=last_piv[0], i1=last_idx,
                   p0=last_piv[1], p1=last_close,
                   up=last_piv[2] == 'L', forming=True)
    legs.append(forming)

    origin_low = seq[0][1]
    # Include the forming leg's current price: when the anchor low is also the most
    # recent pivot (a fresh advance, wave 1 forming), seq holds only that low, so a
    # pivot-only max would equal origin_low and collapse rng — and every Fib level —
    # to a single value. The live high of the current advance defines the range.
    swing_high = max(max(p for _, p, _ in seq), last_close)
    rng = swing_high - origin_low

    # --- core Elliott rule checks on the completed 1..5 (where available) --- #
    def leg_len(lbl):
        for lg in legs:
            if lg['label'] == lbl and not lg['forming']:
                return abs(lg['p1'] - lg['p0'])
        return None
    rule_notes, rules_ok = [], True
    w1, w3, w5 = leg_len('1'), leg_len('3'), leg_len('5')
    if w1 and w3:
        if w3 < w1 and (w5 is None or w3 < w5):
            rules_ok = False; rule_notes.append('wave 3 is the shortest (rule breach)')
        else:
            rule_notes.append('wave 3 is not the shortest ✓')
    # wave 4 must not overlap wave 1 top
    w1_top = next((lg['p1'] for lg in legs if lg['label'] == '1'), None)
    w4_low = next((lg['p1'] for lg in legs if lg['label'] == '4' and not lg['forming']), None)
    if w1_top and w4_low:
        if w4_low > w1_top:
            rule_notes.append('wave 4 holds above wave 1 top ✓')
        else:
            rules_ok = False; rule_notes.append('wave 4 overlaps wave 1 (rule breach)')

    # ------------------------------ signal --------------------------------- #
    # Fibonacci via the shared calculator: retracements of the advance (origin low
    # -> swing high) are the buy-zone; extensions are the upside projections.
    if swing_high > origin_low:
        lv = _FIB.calculate_all_levels(origin_low, swing_high, 'uptrend')
        fib = {f'{r*100:.1f}%': float(lv.retracement_levels[f'R_{r}'])
               for r in (0.236, 0.382, 0.5, 0.618)}
        extensions = {f'{r:.3f}': float(lv.extension_levels[f'E_{r}'])
                      for r in (1.272, 1.618, 2.618)}
        upside_target = extensions['1.618']
    else:
        # degenerate: no measurable advance yet (price at/under the anchor low)
        fib = {f'{p}%': swing_high for p in ('23.6', '38.2', '50.0', '61.8')}
        extensions = {}
        upside_target = swing_high
    invalidation = origin_low

    table = {
        1: ('HOLD', 'Wave 1 forming (base building)',
            'A first advance off the low is underway. Too early to chase; wait for the '
            'wave 2 pullback to position for wave 3.'),
        2: ('BUY', 'Wave 2 pullback',
            'Price is correcting the first advance. Elliott theory places the highest-'
            'reward entry here, ahead of a wave 3.'),
        3: ('BUY / HOLD', 'Wave 3 (strongest wave)',
            'The most powerful, trend-confirming wave is in progress. Stay long; wave 3 '
            'typically extends well beyond the wave 1 high.'),
        4: ('BUY THE DIP', 'Wave 4 pullback',
            'A shallow correction of wave 3 is underway with a wave 5 still expected. '
            'Dip-buyable, but this is the late stage of the advance.'),
        5: ('REDUCE / SELL', 'Wave 5 (impulse ending)',
            'The final leg of the impulse is in progress. Momentum often wanes here; '
            'tighten stops / take profits as an A-B-C correction is due next.'),
        6: ('SELL / AVOID', 'Wave A (correction begun)',
            'The five-wave advance is complete and price is now correcting. Avoid fresh '
            'longs until the correction matures toward Fibonacci support.'),
        7: ('SELL', 'Wave B bounce',
            'A counter-trend bounce inside the correction. Often a bull-trap; sell into '
            'strength rather than buy it.'),
        8: ('BUY (prepare)', 'Wave C (correction ending)',
            'The final corrective leg down is in progress. As it completes near support, '
            'a fresh impulse — and a buying opportunity — sets up.'),
    }
    key = forming_no if forming_no in table else (8 if forming_no > 8 else 1)
    signal, position, rationale = table[key]

    # confidence from rule health + whether wave 3 (if present) is the extended one
    confidence = 'High' if rules_ok and w3 and w1 and w3 >= w1 else ('Low' if not rules_ok else 'Medium')

    return dict(
        df=df, pivots=pivots, legs=legs, forming_no=forming_no,
        last_close=last_close, origin_low=origin_low, swing_high=swing_high, rng=rng,
        signal=signal, position=position, rationale=rationale, confidence=confidence,
        rule_notes=rule_notes, fib=fib, extensions=extensions,
        upside_target=upside_target, invalidation=invalidation,
        w4_low=w4_low,
    )


# ------------------------------- charting ---------------------------------- #
def build_figure(a):
    df = a['df']
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name='Price', increasing_line_color='#26a69a', decreasing_line_color='#ef5350'))

    # wave overlay (labelled legs incl. the forming one)
    xs, ys, texts = [], [], []
    first = a['legs'][0]
    xs.append(pd.Timestamp(df['Date'].iloc[first['i0']]).to_pydatetime()); ys.append(first['p0']); texts.append('')
    for lg in a['legs']:
        xs.append(pd.Timestamp(df['Date'].iloc[lg['i1']]).to_pydatetime())
        ys.append(lg['p1'])
        texts.append(lg['label'] + (' •' if lg['forming'] else ''))
    fig.add_trace(go.Scatter(
        x=xs, y=ys, text=texts, mode='lines+markers+text', name='Elliott count',
        textposition='top center', textfont=dict(size=15, color='#1565c0'),
        line=dict(color='#1565c0', width=2.5), marker=dict(size=8)))

    x0 = pd.Timestamp(df['Date'].iloc[0]).to_pydatetime()
    x1 = pd.Timestamp(df['Date'].iloc[-1]).to_pydatetime()
    for pct, level in a['fib'].items():
        fig.add_shape(type='line', x0=x0, x1=x1, y0=level, y1=level,
                      line=dict(color='rgba(120,120,120,0.5)', width=1, dash='dash'))
        fig.add_annotation(x=x1, y=level, text=f'  {pct} {level:.0f}', showarrow=False,
                           xanchor='left', font=dict(size=10, color='#888'))
    fig.add_shape(type='rect', x0=x0, x1=x1, y0=a['fib']['61.8%'], y1=a['fib']['38.2%'],
                  fillcolor='rgba(38,166,154,0.10)', line_width=0, layer='below')
    for mult, level in a.get('extensions', {}).items():
        primary = abs(level - a['upside_target']) < 1e-9      # 1.618 == headline target
        fig.add_hline(y=level, line=dict(color='#2e7d32', width=1.2 if primary else 0.8,
                                         dash='dot'),
                      annotation_text=f"{mult}× ext {level:.0f}", annotation_position='top left',
                      annotation_font=dict(size=10, color='#2e7d32'))
    fig.add_hline(y=a['invalidation'], line=dict(color='#b71c1c', width=1.2, dash='dot'),
                  annotation_text=f"Invalidation {a['invalidation']:.0f}", annotation_position='bottom left')
    fig.update_layout(template='plotly_white', height=560, margin=dict(l=40, r=90, t=30, b=30),
                      xaxis_rangeslider_visible=False, legend=dict(orientation='h', y=1.02, x=0),
                      hovermode='x unified')
    return fig


# ------------------------------ html report -------------------------------- #
SIGNAL_COLORS = {'BUY': '#1b7f3b', 'BUY / HOLD': '#1b7f3b', 'BUY THE DIP': '#1b7f3b',
                 'BUY (prepare)': '#2e7d32', 'HOLD': '#b8860b',
                 'REDUCE / SELL': '#c0392b', 'SELL / AVOID': '#c0392b', 'SELL': '#c0392b'}


def wave_rows(a):
    rows = ''
    for lg in a['legs']:
        d0 = pd.Timestamp(a['df']['Date'].iloc[lg['i0']]).date()
        d1 = pd.Timestamp(a['df']['Date'].iloc[lg['i1']]).date()
        move = (lg['p1'] - lg['p0']) / lg['p0'] * 100
        tag = ' <span style="color:#1565c0">(forming)</span>' if lg['forming'] else ''
        rows += (f'<tr><td>Wave {lg["label"]}{tag}</td><td>{d0} → {d1}</td>'
                 f'<td>{CURRENCY}{lg["p0"]:.2f} → {CURRENCY}{lg["p1"]:.2f}</td>'
                 f'<td class="{"pos" if move>=0 else "neg"}">{move:+.1f}%</td></tr>')
    return rows


def build_html(a):
    df = a['df']
    chart = build_figure(a).to_html(full_html=False, include_plotlyjs=True)
    color = SIGNAL_COLORS.get(a['signal'], '#555')
    asof = pd.Timestamp(df['Date'].iloc[-1]).date()
    start = pd.Timestamp(df['Date'].iloc[0]).date()
    fib_rows = ''.join(f'<tr><td>{p} retracement</td><td>{CURRENCY}{l:.2f}</td></tr>' for p, l in a['fib'].items())
    if a['w4_low']:
        fib_rows += f'<tr><td>Wave-4 low (classic support)</td><td>{CURRENCY}{a["w4_low"]:.2f}</td></tr>'
    ext_rows = ''.join(f'<tr><td>{m}× extension</td><td class="pos">{CURRENCY}{l:.2f}</td></tr>'
                       for m, l in a['extensions'].items())
    filt = (f'{int(ZIGZAG_PCT*100)}% ZigZag filter' if PIVOT_METHOD == 'zigzag'
            else f'find_peaks · {int(PIVOT_PROMINENCE_PCT*100)}% prominence, {PEAK_DISTANCE}-bar spacing')
    notes = ' · '.join(a['rule_notes']) or 'insufficient completed waves to check rules'

    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TICKER} — Elliott Wave Report</title>
<style>
  :root {{ --fg:#1a1a2e; --muted:#666; --line:#e3e3ea; --card:#fff; --bg:#f5f6fa; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; margin:0; background:var(--bg); color:var(--fg); }}
  .wrap {{ max-width:1080px; margin:0 auto; padding:24px 18px 60px; }}
  header {{ display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:8px; }}
  h1 {{ font-size:25px; margin:0; }}
  .sub {{ color:var(--muted); font-size:14px; }}
  .badge {{ display:inline-block; background:{color}; color:#fff; font-weight:700; font-size:28px; letter-spacing:.5px; padding:14px 26px; border-radius:12px; white-space:nowrap; }}
  .signal-card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:22px; margin:18px 0; display:flex; gap:24px; align-items:center; flex-wrap:wrap; }}
  .signal-meta {{ flex:1; min-width:260px; }}
  .signal-meta .pos {{ font-size:18px; font-weight:600; margin:0 0 6px; }}
  .signal-meta .rat {{ color:#333; font-size:14.5px; line-height:1.55; margin:0; }}
  .conf {{ font-size:13px; color:var(--muted); margin-top:8px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:18px 0; }}
  .stat {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
  .stat .k {{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.4px; }}
  .stat .v {{ font-size:20px; font-weight:700; margin-top:4px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px 20px; margin:18px 0; }}
  h2 {{ font-size:16px; margin:0 0 12px; }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; }}
  th,td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); }}
  th {{ color:var(--muted); font-weight:600; font-size:12.5px; text-transform:uppercase; letter-spacing:.3px; }}
  .pos {{ color:#1b7f3b; }} .neg {{ color:#c0392b; }}
  .disc {{ font-size:12.5px; color:var(--muted); line-height:1.6; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --fg:#e8e8f0; --muted:#9aa; --line:#2a2a3a; --card:#1a1a28; --bg:#101018; }}
    .signal-meta .rat {{ color:#ccd; }}
  }}
</style></head><body><div class="wrap">
  <header>
    <div><h1>{TICKER} · Elliott Wave Analysis</h1>
    <div class="sub">Daily · {start} → {asof} · {len(df)} bars · {filt}</div></div>
    <div class="sub">Last close <b>{CURRENCY}{a['last_close']:.2f}</b></div>
  </header>

  <div class="signal-card">
    <div class="badge">{a['signal']}</div>
    <div class="signal-meta">
      <p class="pos">Current position: {a['position']} &nbsp;·&nbsp; wave {a['forming_no']} forming</p>
      <p class="rat">{a['rationale']}</p>
      <div class="conf">Confidence: <b>{a['confidence']}</b> &nbsp;·&nbsp; rule check: {notes}</div>
    </div>
  </div>

  <div class="grid">
    <div class="stat"><div class="k">Count origin low</div><div class="v">{CURRENCY}{a['origin_low']:.2f}</div></div>
    <div class="stat"><div class="k">Swing high</div><div class="v">{CURRENCY}{a['swing_high']:.2f}</div></div>
    <div class="stat"><div class="k">Upside target</div><div class="v" style="color:#1b7f3b">{CURRENCY}{a['upside_target']:.2f}</div></div>
    <div class="stat"><div class="k">Invalidation</div><div class="v" style="color:#c0392b">{CURRENCY}{a['invalidation']:.2f}</div></div>
  </div>

  <div class="card"><h2>Elliott wave count (swing legs)</h2>
    <table><thead><tr><th>Wave</th><th>Dates</th><th>Price move</th><th>% move</th></tr></thead>
    <tbody>{wave_rows(a)}</tbody></table></div>

  <div class="card"><h2>Fibonacci buy-zone (retracement of the advance)</h2>
    <table><thead><tr><th>Level</th><th>Price</th></tr></thead><tbody>{fib_rows}</tbody></table></div>

  <div class="card"><h2>Upside targets (Fibonacci extensions of the advance)</h2>
    <table><thead><tr><th>Level</th><th>Price</th></tr></thead><tbody>{ext_rows or '<tr><td colspan=2>no measurable advance yet</td></tr>'}</tbody></table></div>

  <div class="card"><h2>Chart</h2>{chart}</div>

  <div class="card"><h2>Method &amp; disclaimer</h2>
  <p class="disc">Significant swings are extracted with the {filt} swing detector; the count is anchored
  at the lowest swing low of the recent advance (the last {RECENT_PIVOTS} swings) and the legs are labelled
  1-2-3-4-5 / A-B-C. Core Elliott rules are checked (wave 2 holds the origin, wave 3 is not the shortest, wave 4 does
  not overlap wave 1). The signal reads the currently-forming leg.
  Elliott wave counts are inherently subjective and are revised as new bars print, and the ZigZag threshold changes
  the count — this is educational analysis, not investment advice.</p></div>
</div></body></html>"""


def main():
    print(f'Loading {TICKER} from {START} ...')
    df = load_data(TICKER, START)
    print(f'  {len(df)} bars, last close {df["Close"].iloc[-1]:.2f} on {df["Date"].iloc[-1].date()}')
    a = analyze(df)
    if a is None:
        print('Not enough swing structure to build a count.')
        return
    print('  legs: ' + ' '.join(f'{lg["label"]}{"(f)" if lg["forming"] else ""}' for lg in a['legs']))
    print(f'  SIGNAL: {a["signal"]} | {a["position"]} | confidence {a["confidence"]}')
    os.makedirs('reports', exist_ok=True)
    out = f'reports/{TICKER}_elliott_report.html'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(build_html(a))
    print(f'Report written: {out}')


if __name__ == '__main__':
    main()
