"""
Elliott Wave impulse scan on an Indian stock: Cupid Ltd (NSE: CUPID.NS).

Downloads daily OHLC data directly from Yahoo Finance via yfinance, converts it
to the column layout this project expects, and scans for valid 12345 impulsive
moves (and leading diagonals) starting from the lowest low in the window.

Run:  python example_cupid_india.py
Charts for each detected pattern are written to the images/ folder.
"""
from __future__ import annotations
from models.WavePattern import WavePattern
from models.WaveRules import Impulse, LeadingDiagonal
from models.WaveAnalyzer import WaveAnalyzer
from models.WaveOptions import WaveOptionsGenerator5
from models.helpers import plot_pattern, convert_yf_data
import pandas as pd
import numpy as np
import yfinance as yf

TICKER = 'CUPID.NS'   # Cupid Ltd on India's National Stock Exchange
START = '2023-01-01'

# Download and normalise the data. Recent yfinance returns MultiIndex columns
# (level 1 is the ticker); flatten to single-level so convert_yf_data works.
raw = yf.download(TICKER, start=START, auto_adjust=False, progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)
df = convert_yf_data(raw)

# optional: keep a local copy for reproducible reruns
df.to_csv(r'data\cupid_ns_1d.csv', sep=",", index=False)

idx_start = int(np.argmin(np.array(list(df['Low']))))

wa = WaveAnalyzer(df=df, verbose=False)
wave_options_impulse = WaveOptionsGenerator5(up_to=15)

impulse = Impulse('impulse')
leading_diagonal = LeadingDiagonal('leading diagonal')
rules_to_check = [impulse, leading_diagonal]

print(f'{TICKER}: {len(df)} daily bars from {df["Date"].iloc[0].date()} to {df["Date"].iloc[-1].date()}')
print(f'Lowest low at idx: {idx_start} ({df["Date"].iloc[idx_start].date()}, {df["Low"].iloc[idx_start]:.2f})')
print(f'will run up to {wave_options_impulse.number / 1e6}M combinations.')

wavepatterns_up = set()

for new_option_impulse in wave_options_impulse.options_sorted:

    waves_up = wa.find_impulsive_wave(idx_start=idx_start, wave_config=new_option_impulse.values)

    if waves_up:
        wavepattern_up = WavePattern(waves_up, verbose=True)

        for rule in rules_to_check:

            if wavepattern_up.check_rule(rule):
                if wavepattern_up in wavepatterns_up:
                    continue
                else:
                    wavepatterns_up.add(wavepattern_up)
                    print(f'{rule.name} found: {new_option_impulse.values}')
                    plot_pattern(df=df, wave_pattern=wavepattern_up, title=f'{TICKER} {new_option_impulse}')

print(f'Done. {len(wavepatterns_up)} unique pattern(s) found.')
