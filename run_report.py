"""
Elliott Wave HTML report CLI.

Runs elliott_wave_report.py against any Yahoo Finance ticker (or a named preset)
and writes one self-contained HTML report per swing detector into reports/.

Examples:
  python run_report.py gold                    # preset: GC=F, USD, from 2015
  python run_report.py silver --method peaks
  python run_report.py BTC-USD --start 2022-01-01
  python run_report.py CUPID.NS --currency INR
"""
from __future__ import annotations
import argparse
import os
import sys
import elliott_wave_report as ewr

# Windows consoles default to cp1252, which cannot encode ₹ / · — force UTF-8 so
# printing an INR ticker's status line doesn't crash the run.
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Friendly aliases -> sensible defaults. XAUUSD spot is not on Yahoo, so gold
# uses COMEX GC=F (~ spot minus basis).
PRESETS = {
    'silver':  dict(ticker='SI=F',     currency='$', start='2023-01-01'),
    'gold':    dict(ticker='GC=F',     currency='$', start='2015-01-01'),
    'btc':     dict(ticker='BTC-USD',  currency='$', start='2022-01-01'),
    'bitcoin': dict(ticker='BTC-USD',  currency='$', start='2022-01-01'),
    'cupid':   dict(ticker='CUPID.NS', currency='₹', start='2025-01-01'),
}


def resolve(name: str) -> dict:
    """Map a preset name or raw ticker to a {ticker, currency, start} config."""
    if name.lower() in PRESETS:
        return dict(PRESETS[name.lower()])
    # raw ticker: infer currency from an NSE suffix, default to a wide window
    currency = '₹' if name.upper().endswith('.NS') else '$'
    return dict(ticker=name, currency=currency, start='2020-01-01')


def generate(ticker: str, currency: str, start: str, method: str) -> str | None:
    """Build one report for a single swing detector; returns the output path."""
    ewr.TICKER, ewr.CURRENCY, ewr.START, ewr.PIVOT_METHOD = ticker, currency, start, method
    df = ewr.load_data(ticker, start)
    a = ewr.analyze(df)
    if a is None:
        print(f'[{method}] not enough swing structure to build a count.')
        return None
    legs = ' '.join(f'{lg["label"]}{"(f)" if lg["forming"] else ""}' for lg in a['legs'])
    print(f'[{method}] legs: {legs} | {a["signal"]} | {a["position"]} | confidence {a["confidence"]}')
    os.makedirs('reports', exist_ok=True)
    safe = ticker.replace('=', '').replace('/', '_')
    out = f'reports/{safe}_{method}_elliott_report.html'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(ewr.build_html(a))
    print(f'  report written: {out}')
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description='Elliott Wave HTML report generator.')
    p.add_argument('instrument',
                   help='preset (%s) or any Yahoo Finance ticker' % ', '.join(PRESETS))
    p.add_argument('--method', choices=['peaks', 'zigzag', 'both'], default='both',
                   help='swing detector to run (default: both)')
    p.add_argument('--currency', help='price-symbol override (default: preset, or ₹ for .NS else $)')
    p.add_argument('--start', help='history start YYYY-MM-DD (default: preset, else 2020-01-01)')
    args = p.parse_args(argv)

    cfg = resolve(args.instrument)
    if args.currency:
        cfg['currency'] = args.currency
    if args.start:
        cfg['start'] = args.start

    methods = ['zigzag', 'peaks'] if args.method == 'both' else [args.method]
    print(f'{cfg["ticker"]} · from {cfg["start"]} · {cfg["currency"]}')
    for method in methods:
        generate(cfg['ticker'], cfg['currency'], cfg['start'], method)


if __name__ == '__main__':
    main()
