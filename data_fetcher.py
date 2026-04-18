"""
주가 데이터 수집 모듈
---------------------
- 한국 종목: FinanceDataReader 사용 (pykrx 대체 가능)
- 미국 종목: yfinance 사용
둘 다 OHLCV(시고저종거) DataFrame을 반환합니다.
"""

from datetime import datetime, timedelta
import pandas as pd


def fetch_kr(ticker: str, lookback_days: int = 300) -> pd.DataFrame:
    """한국 종목 주가 데이터 수집."""
    import FinanceDataReader as fdr

    end = datetime.today()
    start = end - timedelta(days=lookback_days)
    df = fdr.DataReader(ticker, start, end)
    # 컬럼 표준화
    df = df.rename(columns={
        "Open": "Open", "High": "High", "Low": "Low",
        "Close": "Close", "Volume": "Volume",
    })
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


def fetch_us(ticker: str, lookback_days: int = 300) -> pd.DataFrame:
    """미국 종목 주가 데이터 수집."""
    import yfinance as yf

    end = datetime.today()
    start = end - timedelta(days=lookback_days)
    df = yf.download(
        ticker,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )
    if df.empty:
        return df
    # yfinance가 MultiIndex로 반환하는 경우 flatten
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


def fetch(ticker: str, market: str, lookback_days: int = 300) -> pd.DataFrame:
    """시장에 맞게 데이터를 가져옵니다."""
    if market.upper() == "KR":
        return fetch_kr(ticker, lookback_days)
    elif market.upper() == "US":
        return fetch_us(ticker, lookback_days)
    else:
        raise ValueError(f"알 수 없는 시장: {market}")
