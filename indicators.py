"""
기술적 지표 계산 모듈
---------------------
pandas만 사용하여 주요 지표를 계산합니다.
- 이동평균 (SMA)
- RSI (Relative Strength Index)
- 볼린저밴드 (Bollinger Bands)
- MACD
"""

import pandas as pd
import numpy as np


def sma(series: pd.Series, period: int) -> pd.Series:
    """단순 이동평균."""
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """지수 이동평균."""
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI 계산."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Wilder smoothing
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    out = 100 - (100 / (1 + rs))
    # 손실이 전혀 없으면 RSI = 100, 이익이 전혀 없으면 RSI = 0
    out = out.where(avg_loss != 0, 100.0)
    out = out.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)
    return out


def bollinger_bands(series: pd.Series, period: int = 20, num_std: float = 2.0):
    """볼린저밴드 (중심선, 상단, 하단, %B)."""
    middle = sma(series, period)
    std = series.rolling(window=period, min_periods=period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    # %B: 밴드 내 위치 (0~1, 넘어가면 음수/1 초과)
    percent_b = (series - lower) / (upper - lower)
    return middle, upper, lower, percent_b


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD 계산 (MACD선, 시그널선, 히스토그램)."""
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_all(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """설정(config)에 따라 모든 지표를 계산해 DataFrame에 컬럼으로 추가."""
    out = df.copy()
    close = out["Close"]

    out[f"MA{cfg.MA_SHORT}"] = sma(close, cfg.MA_SHORT)
    out[f"MA{cfg.MA_LONG}"] = sma(close, cfg.MA_LONG)

    out["RSI"] = rsi(close, cfg.RSI_PERIOD)

    bb_mid, bb_up, bb_low, bb_pct = bollinger_bands(close, cfg.BB_PERIOD, cfg.BB_STD)
    out["BB_MID"] = bb_mid
    out["BB_UP"] = bb_up
    out["BB_LOW"] = bb_low
    out["BB_PCT"] = bb_pct

    macd_line, signal_line, hist = macd(close, cfg.MACD_FAST, cfg.MACD_SLOW, cfg.MACD_SIGNAL)
    out["MACD"] = macd_line
    out["MACD_SIGNAL"] = signal_line
    out["MACD_HIST"] = hist

    return out
