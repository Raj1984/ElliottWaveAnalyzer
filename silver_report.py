"""
Elliott Wave BUY/SELL HTML report for Silver (COMEX front-month, SI=F).

Reuses elliott_wave_report.py (swing count + signal engine), overriding the
ticker/currency/window for silver. Emits one report per swing detector so the
ZigZag and scipy find_peaks counts can be compared side by side.

Run:  python silver_report.py
Output: reports/SI=F_<method>_elliott_report.html
"""
import os
import elliott_wave_report as ewr

ewr.TICKER = 'SI=F'      # COMEX silver front-month future
ewr.CURRENCY = '$'
ewr.START = '2023-01-01'


def generate(method: str):
    ewr.PIVOT_METHOD = method
    df = ewr.load_data(ewr.TICKER, ewr.START)
    a = ewr.analyze(df)
    if a is None:
        print(f'[{method}] not enough swing structure to build a count.')
        return
    legs = ' '.join(f'{lg["label"]}{"(f)" if lg["forming"] else ""}' for lg in a['legs'])
    print(f'[{method}] legs: {legs} | {a["signal"]} | {a["position"]} | confidence {a["confidence"]}')
    os.makedirs('reports', exist_ok=True)
    out = f'reports/{ewr.TICKER}_{method}_elliott_report.html'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(ewr.build_html(a))
    print(f'  report written: {out}')


if __name__ == '__main__':
    for method in ('zigzag', 'peaks'):
        generate(method)
