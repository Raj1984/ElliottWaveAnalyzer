"""
Elliott Wave BUY/SELL HTML report for Gold (spot XAUUSD).

Reuses elliott_wave_report.py (swing count + signal engine + Frost & Prechter
book overlay), overriding the ticker/currency/window for gold. Emits one report
per swing detector so the ZigZag and scipy find_peaks counts can be compared.

Run:  python gold_report.py
Output: reports/<TICKER>_<method>_elliott_report.html
"""
import os
import elliott_wave_report as ewr

ewr.TICKER = 'GC=F'           # COMEX gold futures (spot XAUUSD is not on Yahoo; GC=F ~ spot minus basis)
ewr.CURRENCY = '$'
ewr.START = '2015-01-01'       # capture the 2015 cycle low (~$1046) for the primary impulse


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
    safe = ewr.TICKER.replace('=', '')
    out = f'reports/{safe}_{method}_elliott_report.html'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(ewr.build_html(a))
    print(f'  report written: {out}')


if __name__ == '__main__':
    for method in ('zigzag', 'peaks'):
        generate(method)
