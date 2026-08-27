from models.WavePattern import WavePattern
import pandas as pd
import time
import atexit
import plotly.graph_objects as go
import kaleido
import os
import random
import string


# Reuse a single persistent kaleido browser for all image exports instead of
# letting each fig.write_image() spin up and tear down its own Chrome subprocess.
# The per-call churn is slow and, under kaleido 1.x, intermittently crashes on
# browser teardown ("Couldn't close or kill browser subprocess"), leaving a hung
# process. Starting the sync server once routes every write_fig_sync() through
# the same browser; it is torn down a single time at interpreter exit.
_kaleido_server_started = False


def _ensure_kaleido_server():
    global _kaleido_server_started
    if not _kaleido_server_started:
        kaleido.start_sync_server()
        atexit.register(_stop_kaleido_server)
        _kaleido_server_started = True


def _stop_kaleido_server():
    try:
        kaleido.stop_sync_server(silence_warnings=True)
    except Exception:
        # A failed teardown at exit is harmless: the process is ending anyway.
        pass


def timeit(func):
    def wrapper(*arg, **kw):

        t1 = time.perf_counter_ns()
        res = func(*arg, **kw)
        t2 = time.perf_counter_ns()
        print("took:", t2-t1, 'ns')
        return res
    return wrapper


def plot_cycle(df, wave_cycle, title: str = ''):

    data = go.Ohlc(x=df['Date'],
                   open=df['Open'],
                   high=df['High'],
                   low=df['Low'],
                   close=df['Close'])

    monowaves = go.Scatter(x=wave_cycle.dates,
                           y=wave_cycle.values,
                           text=wave_cycle.labels,
                           mode='lines+markers+text',
                           textposition='middle right',
                           textfont=dict(size=15, color='#2c3035'),
                           line=dict(
                               color=('rgb(111, 126, 130)'),
                               width=3),
                           )
    layout = dict(title=title)
    fig = go.Figure(data=[data, monowaves], layout=layout)
    fig.update(layout_xaxis_rangeslider_visible=False)

    save_chart_as_image(fig)
    #fig.show()


def convert_yf_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts a yahoo finance OHLC DataFrame to column name(s) used in this project

    old_names = ['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
    new_names = ['Date', 'Open', 'High', 'Low', 'Close']

    :param df:
    :return:
    """
    df_output = pd.DataFrame()

    df_output['Date'] = list(df.index)
    df_output['Date'] = pd.to_datetime(df_output['Date'], format="%Y-%m-%d %H:%M:%S")

    df_output['Open'] = df['Open'].to_list()
    df_output['High'] = df['High'].to_list()
    df_output['Low'] = df['Low'].to_list()
    df_output['Close'] = df['Close'].to_list()


    return df_output

def _json_safe_dates(dates):
    """
    Make a list of wave x-values safe for kaleido's image export.

    A wave's `.dates` is a plain Python list. When it holds pandas Timestamp
    objects (e.g. data loaded via convert_yf_data / pd.to_datetime), kaleido
    1.x serializes the figure with orjson, which cannot encode a Timestamp.
    The failure is swallowed inside kaleido's worker, so write_fig_sync writes
    no file and raises nothing. Converting to native python datetimes keeps
    both plotly and orjson happy. Plain date strings (as used by the CSV
    examples) are already serializable and pass through unchanged.
    """
    converted = []
    for d in dates:
        if isinstance(d, str):
            converted.append(d)
        else:
            converted.append(pd.Timestamp(d).to_pydatetime())
    return converted


def plot_pattern(df: pd.DataFrame, wave_pattern: WavePattern, title: str = ''):
    data = go.Ohlc(x=df['Date'],
                   open=df['Open'],
                   high=df['High'],
                   low=df['Low'],
                   close=df['Close'])

    monowaves = go.Scatter(x=_json_safe_dates(wave_pattern.dates),
                           y=wave_pattern.values,
                           text=wave_pattern.labels,
                           mode='lines+markers+text',
                           textposition='middle right',
                           textfont=dict(size=15, color='#2c3035'),
                           line=dict(
                               color=('rgb(111, 126, 130)'),
                               width=3),
                           )
    layout = dict(title=title)
    fig = go.Figure(data=[data, monowaves], layout=layout)
    fig.update(layout_xaxis_rangeslider_visible=False)

    save_chart_as_image(fig)
    #fig.show()


def plot_monowave(df, monowave, title: str = ''):
    data = go.Ohlc(x=df['Date'],
                   open=df['Open'],
                   high=df['High'],
                   low=df['Low'],
                   close=df['Close'])

    monowaves = go.Scatter(x=_json_safe_dates(monowave.dates),
                           y=monowave.points,
                           mode='lines+markers+text',
                           textposition='middle right',
                           textfont=dict(size=15, color='#2c3035'),
                           line=dict(
                               color=('rgb(111, 126, 130)'),
                               width=3),
                           )
    layout = dict(title=title)
    fig = go.Figure(data=[data, monowaves], layout=layout)
    fig.update(layout_xaxis_rangeslider_visible=False)

    save_chart_as_image(fig)
    # fig.show()

def save_chart_as_image(fig):
    if not os.path.exists("images"):
        os.mkdir("images")
    current_timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    filename = f"./images/{current_timestamp}_{generate_random_string(6)}.png"
    _ensure_kaleido_server()
    kaleido.write_fig_sync(fig, filename)


def generate_random_string(length) -> str:
    # Define the character set (lowercase, uppercase, digits, and punctuation)
    characters = string.digits
    # Generate a random string
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string