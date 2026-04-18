"""
신호 생성 및 점수화 모듈
-------------------------
각 기술적 지표에서 나온 신호를 +1/0/-1로 환산하고
종합 점수를 계산합니다.

주의: 이 점수는 교육/연습 목적의 참고용이며,
실제 매매에 사용할 시 손실 위험이 있습니다.
"""

import pandas as pd


def last_two(series: pd.Series):
    """마지막 두 값 반환 (교차 판정용)."""
    if len(series.dropna()) < 2:
        return None, None
    vals = series.dropna().iloc[-2:]
    return vals.iloc[0], vals.iloc[1]


def signal_ma_cross(df: pd.DataFrame, short_col: str, long_col: str) -> dict:
    """이동평균 골든/데드 크로스."""
    s_prev, s_now = last_two(df[short_col])
    l_prev, l_now = last_two(df[long_col])
    if None in (s_prev, s_now, l_prev, l_now):
        return {"score": 0, "note": f"{short_col}/{long_col}: 데이터 부족"}

    if s_prev <= l_prev and s_now > l_now:
        return {"score": 2, "note": f"🟢 골든크로스 ({short_col}↗{long_col})"}
    if s_prev >= l_prev and s_now < l_now:
        return {"score": -2, "note": f"🔴 데드크로스 ({short_col}↘{long_col})"}
    if s_now > l_now:
        return {"score": 1, "note": f"단기MA > 장기MA (상승추세)"}
    return {"score": -1, "note": f"단기MA < 장기MA (하락추세)"}


def signal_rsi(df: pd.DataFrame, oversold: float, overbought: float) -> dict:
    """RSI 과매도/과매수."""
    if df["RSI"].dropna().empty:
        return {"score": 0, "note": "RSI: 데이터 부족"}
    val = df["RSI"].dropna().iloc[-1]
    if val < oversold:
        return {"score": 2, "note": f"🟢 RSI {val:.1f} (과매도, 반등 가능)"}
    if val > overbought:
        return {"score": -2, "note": f"🔴 RSI {val:.1f} (과매수, 조정 가능)"}
    if val < 45:
        return {"score": 1, "note": f"RSI {val:.1f} (중립, 약한 상승 여지)"}
    if val > 55:
        return {"score": -1, "note": f"RSI {val:.1f} (중립, 약한 하락 여지)"}
    return {"score": 0, "note": f"RSI {val:.1f} (중립)"}


def signal_bollinger(df: pd.DataFrame) -> dict:
    """볼린저밴드 %B 기준."""
    if df["BB_PCT"].dropna().empty:
        return {"score": 0, "note": "볼린저: 데이터 부족"}
    pct = df["BB_PCT"].dropna().iloc[-1]
    if pct < 0:
        return {"score": 2, "note": f"🟢 하단 밴드 이탈 (%B={pct:.2f})"}
    if pct > 1:
        return {"score": -2, "note": f"🔴 상단 밴드 이탈 (%B={pct:.2f})"}
    if pct < 0.2:
        return {"score": 1, "note": f"하단 근접 (%B={pct:.2f})"}
    if pct > 0.8:
        return {"score": -1, "note": f"상단 근접 (%B={pct:.2f})"}
    return {"score": 0, "note": f"중립 (%B={pct:.2f})"}


def signal_macd(df: pd.DataFrame) -> dict:
    """MACD 히스토그램 부호 전환."""
    h_prev, h_now = last_two(df["MACD_HIST"])
    if h_prev is None or h_now is None:
        return {"score": 0, "note": "MACD: 데이터 부족"}

    if h_prev <= 0 and h_now > 0:
        return {"score": 2, "note": f"🟢 MACD 상향전환 (hist {h_now:+.2f})"}
    if h_prev >= 0 and h_now < 0:
        return {"score": -2, "note": f"🔴 MACD 하향전환 (hist {h_now:+.2f})"}
    if h_now > 0:
        return {"score": 1, "note": f"MACD 양(+), 모멘텀 유지"}
    return {"score": -1, "note": f"MACD 음(-), 약세 유지"}


def analyze(df: pd.DataFrame, cfg) -> dict:
    """모든 신호를 종합해 점수와 메시지 반환."""
    results = [
        signal_ma_cross(df, f"MA{cfg.MA_SHORT}", f"MA{cfg.MA_LONG}"),
        signal_rsi(df, cfg.RSI_OVERSOLD, cfg.RSI_OVERBOUGHT),
        signal_bollinger(df),
        signal_macd(df),
    ]
    total = sum(r["score"] for r in results)
    notes = [r["note"] for r in results]
    last_close = df["Close"].iloc[-1]
    prev_close = df["Close"].iloc[-2] if len(df) >= 2 else last_close
    change_pct = (last_close / prev_close - 1) * 100

    if total >= cfg.SCORE_THRESHOLD_BUY:
        verdict = "📈 상승 신호"
    elif total <= cfg.SCORE_THRESHOLD_SELL:
        verdict = "📉 하락 신호"
    else:
        verdict = "➖ 중립"

    return {
        "last_close": float(last_close),
        "change_pct": float(change_pct),
        "score": total,
        "verdict": verdict,
        "notes": notes,
    }
