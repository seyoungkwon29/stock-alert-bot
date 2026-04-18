"""
급등 후보 스크리너
------------------
yfinance에서 가져올 수 있는 무료 데이터를 종합 분석하여
당일 급등 가능성이 높은 미국 종목을 점수화합니다.

분석 지표:
  1. 거래량 급등 (20일 평균 대비)
  2. 공매도 비율 (숏스퀴즈 후보)
  3. RSI 과매도 반등
  4. MACD 상향전환
  5. 볼린저밴드 스퀴즈 (변동성 축소→확장)
  6. 연속 하락 후 반등 (평균회귀)
  7. 52주 저점 근접도

⚠️ 교육/연습용이며 투자 자문이 아닙니다.
"""

from __future__ import annotations

import traceback
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

from indicators import sma, rsi, bollinger_bands, macd


def _fetch_batch(tickers: list[str], days: int = 300) -> dict[str, pd.DataFrame]:
    """yfinance 일괄 다운로드 후 종목별 DataFrame으로 분리."""
    end = datetime.today()
    start = end - timedelta(days=days)
    raw = yf.download(
        tickers,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
        group_by="ticker",
        threads=True,
    )
    result = {}
    for t in tickers:
        try:
            if len(tickers) == 1:
                df = raw.copy()
            else:
                df = raw[t].copy()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
            if len(df) >= 60:
                result[t] = df
        except Exception:
            pass
    return result


def _get_short_info(tickers: list[str]) -> dict[str, dict]:
    """yfinance에서 공매도/펀더멘털 정보 수집."""
    info_map = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            info = tk.info or {}
            info_map[t] = {
                "short_pct": info.get("shortPercentOfFloat", 0) or 0,
                "short_ratio": info.get("shortRatio", 0) or 0,
                "name": info.get("shortName", t),
                "week52_low": info.get("fiftyTwoWeekLow", 0) or 0,
                "week52_high": info.get("fiftyTwoWeekHigh", 0) or 0,
                "market_cap": info.get("marketCap", 0) or 0,
            }
        except Exception:
            info_map[t] = {
                "short_pct": 0, "short_ratio": 0, "name": t,
                "week52_low": 0, "week52_high": 0, "market_cap": 0,
            }
    return info_map


# ---------------------------------------------------------------
# 개별 지표 점수 함수
# ---------------------------------------------------------------

def score_volume(df: pd.DataFrame, cfg) -> dict:
    """거래량 급등 점수."""
    vol = df["Volume"]
    avg_vol = vol.rolling(20).mean()
    if avg_vol.dropna().empty or avg_vol.iloc[-1] == 0:
        return {"score": 0, "note": "거래량 데이터 부족"}
    ratio = vol.iloc[-1] / avg_vol.iloc[-1]
    if ratio >= cfg.SURGE_VOL_RATIO_STRONG:
        return {"score": 3, "note": f"🔥 거래량 {ratio:.1f}배 폭증"}
    if ratio >= cfg.SURGE_VOL_RATIO_MID:
        return {"score": 2, "note": f"📊 거래량 {ratio:.1f}배 급증"}
    if ratio >= cfg.SURGE_VOL_RATIO_WEAK:
        return {"score": 1, "note": f"거래량 {ratio:.1f}배 증가"}
    return {"score": 0, "note": f"거래량 평이 ({ratio:.1f}배)"}


def score_short_interest(info: dict, cfg) -> dict:
    """공매도 비율 점수 (숏스퀴즈 가능성)."""
    pct = info["short_pct"] * 100 if info["short_pct"] < 1 else info["short_pct"]
    if pct >= cfg.SURGE_SHORT_HIGH:
        return {"score": 3, "note": f"🔥 공매도 {pct:.1f}% (스퀴즈 후보)"}
    if pct >= cfg.SURGE_SHORT_MID:
        return {"score": 2, "note": f"📊 공매도 {pct:.1f}%"}
    if pct >= 5:
        return {"score": 1, "note": f"공매도 {pct:.1f}%"}
    if pct > 0:
        return {"score": 0, "note": f"공매도 {pct:.1f}% (낮음)"}
    return {"score": 0, "note": "공매도 정보 없음"}


def score_rsi_bounce(df: pd.DataFrame, cfg) -> dict:
    """RSI 과매도 반등 점수."""
    rsi_vals = rsi(df["Close"], cfg.RSI_PERIOD)
    if rsi_vals.dropna().empty:
        return {"score": 0, "note": "RSI 데이터 부족"}
    curr = rsi_vals.iloc[-1]
    prev = rsi_vals.iloc[-2] if len(rsi_vals.dropna()) >= 2 else curr
    # 과매도에서 반등 시작
    if curr < 30:
        if curr > prev:
            return {"score": 3, "note": f"🟢 RSI {curr:.1f} 과매도 반등 시작"}
        return {"score": 2, "note": f"🟢 RSI {curr:.1f} 과매도 구간"}
    if curr < 40 and prev < 30:
        return {"score": 2, "note": f"RSI {curr:.1f} (과매도 탈출 중)"}
    if curr < 40:
        return {"score": 1, "note": f"RSI {curr:.1f} (저평가 구간)"}
    return {"score": 0, "note": f"RSI {curr:.1f}"}


def score_macd_cross(df: pd.DataFrame, cfg) -> dict:
    """MACD 상향전환 점수."""
    _, _, hist = macd(df["Close"], cfg.MACD_FAST, cfg.MACD_SLOW, cfg.MACD_SIGNAL)
    if hist.dropna().empty or len(hist.dropna()) < 2:
        return {"score": 0, "note": "MACD 데이터 부족"}
    h_prev, h_now = hist.dropna().iloc[-2], hist.dropna().iloc[-1]
    if h_prev <= 0 and h_now > 0:
        return {"score": 3, "note": f"🟢 MACD 골든크로스 ({h_now:+.3f})"}
    if h_now > h_prev and h_now > 0:
        return {"score": 1, "note": f"MACD 상승 모멘텀 ({h_now:+.3f})"}
    if h_now > h_prev and h_prev < 0:
        return {"score": 2, "note": f"MACD 반등 중 ({h_now:+.3f})"}
    return {"score": 0, "note": f"MACD ({h_now:+.3f})"}


def score_bb_squeeze(df: pd.DataFrame, cfg) -> dict:
    """볼린저밴드 스퀴즈 (변동성 축소 후 확장)."""
    mid, upper, lower, pct_b = bollinger_bands(df["Close"], cfg.BB_PERIOD, cfg.BB_STD)
    if upper.dropna().empty or len(upper.dropna()) < 20:
        return {"score": 0, "note": "볼린저 데이터 부족"}
    bandwidth = (upper - lower) / mid
    bw_now = bandwidth.iloc[-1]
    bw_avg = bandwidth.rolling(20).mean().iloc[-1]
    pct_now = pct_b.iloc[-1]

    # 밴드폭이 평균보다 좁으면 → 스퀴즈 (곧 큰 움직임 예고)
    if bw_now < bw_avg * 0.7 and pct_now < 0.3:
        return {"score": 2, "note": f"🔸 밴드 스퀴즈 + 하단 근접 (%B={pct_now:.2f})"}
    if pct_now < 0:
        return {"score": 2, "note": f"🟢 하단 이탈 (%B={pct_now:.2f})"}
    if pct_now < 0.2:
        return {"score": 1, "note": f"하단 근접 (%B={pct_now:.2f})"}
    return {"score": 0, "note": f"볼린저 중립 (%B={pct_now:.2f})"}


def score_consecutive_down(df: pd.DataFrame, cfg) -> dict:
    """연속 하락 후 반등 (평균회귀)."""
    closes = df["Close"].tail(cfg.SURGE_CONSEC_DOWN_DAYS + 2)
    changes = closes.pct_change().dropna()
    if len(changes) < cfg.SURGE_CONSEC_DOWN_DAYS:
        return {"score": 0, "note": "데이터 부족"}

    recent = changes.iloc[-(cfg.SURGE_CONSEC_DOWN_DAYS + 1):]
    down_streak = sum(1 for c in recent.iloc[:-1] if c < 0)
    last_change = recent.iloc[-1]

    if down_streak >= cfg.SURGE_CONSEC_DOWN_DAYS and last_change > 0:
        return {"score": 3, "note": f"🔄 {down_streak}일 연속하락 후 반등 ({last_change:+.1%})"}
    if down_streak >= cfg.SURGE_CONSEC_DOWN_DAYS:
        return {"score": 2, "note": f"📉 {down_streak}일 연속하락 (반등 대기)"}
    return {"score": 0, "note": ""}


def score_52w_proximity(df: pd.DataFrame, info: dict) -> dict:
    """52주 저점 근접도."""
    low = info["week52_low"]
    high = info["week52_high"]
    if not low or not high or high == low:
        return {"score": 0, "note": "52주 데이터 없음"}
    curr = df["Close"].iloc[-1]
    position = (curr - low) / (high - low)
    if position < 0.1:
        return {"score": 2, "note": f"📍 52주 저점 근접 ({position:.0%} 위치)"}
    if position < 0.2:
        return {"score": 1, "note": f"52주 하단권 ({position:.0%} 위치)"}
    return {"score": 0, "note": f"52주 {position:.0%} 위치"}


# ---------------------------------------------------------------
# 메인 스크리너
# ---------------------------------------------------------------

def run_surge_screen(cfg, top_n: int | None = None) -> list[dict]:
    """전체 스캔 실행, 점수 높은 순으로 정렬 반환."""
    tickers = cfg.SURGE_UNIVERSE
    top_n = top_n or cfg.SURGE_TOP_N

    print(f"📡 {len(tickers)}개 종목 가격 데이터 수집 중...")
    price_data = _fetch_batch(tickers, cfg.LOOKBACK_DAYS)
    print(f"   {len(price_data)}개 종목 수집 완료")

    print("📡 공매도/펀더멘털 정보 수집 중...")
    info_data = _get_short_info(list(price_data.keys()))
    print(f"   정보 수집 완료\n")

    results = []
    for ticker, df in price_data.items():
        try:
            info = info_data.get(ticker, {
                "short_pct": 0, "short_ratio": 0, "name": ticker,
                "week52_low": 0, "week52_high": 0, "market_cap": 0,
            })

            scores = [
                ("거래량", score_volume(df, cfg)),
                ("공매도", score_short_interest(info, cfg)),
                ("RSI", score_rsi_bounce(df, cfg)),
                ("MACD", score_macd_cross(df, cfg)),
                ("볼린저", score_bb_squeeze(df, cfg)),
                ("연속하락", score_consecutive_down(df, cfg)),
                ("52주저점", score_52w_proximity(df, info)),
            ]

            total = sum(s[1]["score"] for s in scores)
            notes = [s[1]["note"] for s in scores if s[1]["score"] > 0]

            last_close = df["Close"].iloc[-1]
            prev_close = df["Close"].iloc[-2] if len(df) >= 2 else last_close
            change_pct = (last_close / prev_close - 1) * 100

            results.append({
                "ticker": ticker,
                "name": info.get("name", ticker),
                "score": total,
                "last_close": float(last_close),
                "change_pct": float(change_pct),
                "short_pct": info["short_pct"] * 100 if info["short_pct"] < 1 else info["short_pct"],
                "notes": notes,
                "detail": {s[0]: s[1] for s in scores},
            })

            verdict = "🔥" if total >= 5 else "📈" if total >= 3 else "  "
            print(f"  {verdict} [{ticker:6s}] {info.get('name', ''):20s}  점수={total:+2d}  종가={last_close:>10.2f} ({change_pct:+.1f}%)")

        except Exception as e:
            print(f"  ❌ [{ticker}] 오류: {e}")

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]


def format_surge_report(date_str: str, results: list[dict]) -> str:
    """급등 후보 스크리너 결과를 카카오톡 메시지로 포맷."""
    if not results:
        return f"🔍 {date_str} 급등 후보 스크리너\n\n조건을 충족하는 종목이 없습니다."

    lines = [f"🔍 {date_str} 급등 후보 TOP {len(results)}"]
    lines.append("")

    for i, r in enumerate(results, 1):
        medal = "🥇🥈🥉"[i - 1] if i <= 3 else f"{i}."
        lines.append(f"{medal} {r['name']} ({r['ticker']})  점수 {r['score']:+d}")
        lines.append(f"   종가 ${r['last_close']:,.2f} ({r['change_pct']:+.1f}%)")
        if r["short_pct"] > 0:
            lines.append(f"   공매도 {r['short_pct']:.1f}%")
        for note in r["notes"]:
            lines.append(f"   • {note}")
        lines.append("")

    lines.append("⚠️ 교육용 참고 자료이며 투자 권유가 아닙니다.")
    return "\n".join(lines)
