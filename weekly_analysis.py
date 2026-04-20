"""
주간 분석 모듈 (월요일용)
-------------------------
금요일까지의 주간 흐름을 분석하고
이번 주 강세 예상 종목을 추천합니다.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from data_fetcher import fetch
from indicators import sma, rsi, macd, bollinger_bands


def _weekly_change(df: pd.DataFrame, days: int = 5) -> float:
    """최근 N거래일 수익률."""
    if len(df) < days + 1:
        return 0.0
    return (df["Close"].iloc[-1] / df["Close"].iloc[-(days + 1)] - 1) * 100


def _weekly_volume_trend(df: pd.DataFrame, days: int = 5) -> float:
    """최근 N거래일 평균 거래량 vs 이전 20일 평균."""
    if len(df) < 25:
        return 1.0
    recent_avg = df["Volume"].iloc[-days:].mean()
    prev_avg = df["Volume"].iloc[-(days + 20):-days].mean()
    if prev_avg == 0:
        return 1.0
    return recent_avg / prev_avg


def _consecutive_direction(df: pd.DataFrame, days: int = 5) -> tuple[int, int]:
    """최근 N거래일 중 상승일/하락일 수."""
    changes = df["Close"].pct_change().iloc[-days:]
    up = (changes > 0).sum()
    down = (changes < 0).sum()
    return int(up), int(down)


def analyze_weekly(ticker: str, name: str, market: str, cfg) -> dict | None:
    """한 종목의 주간 분석."""
    try:
        df = fetch(ticker, market, cfg.LOOKBACK_DAYS)
        if df.empty or len(df) < 60:
            return None

        close = df["Close"]
        weekly_chg = _weekly_change(df, 5)
        vol_ratio = _weekly_volume_trend(df, 5)
        up_days, down_days = _consecutive_direction(df, 5)

        # RSI
        rsi_vals = rsi(close, cfg.RSI_PERIOD)
        curr_rsi = rsi_vals.iloc[-1] if not rsi_vals.dropna().empty else 50

        # MACD
        _, _, hist = macd(close, cfg.MACD_FAST, cfg.MACD_SLOW, cfg.MACD_SIGNAL)
        macd_trend = ""
        if len(hist.dropna()) >= 5:
            recent_hist = hist.dropna().iloc[-5:]
            if recent_hist.iloc[-1] > recent_hist.iloc[0]:
                macd_trend = "상승 모멘텀"
            else:
                macd_trend = "하락 모멘텀"

        # 볼린저밴드
        _, bb_up, bb_low, pct_b = bollinger_bands(close, cfg.BB_PERIOD, cfg.BB_STD)
        curr_pctb = pct_b.iloc[-1] if not pct_b.dropna().empty else 0.5

        # MA 위치
        ma_short = sma(close, cfg.MA_SHORT)
        ma_long = sma(close, cfg.MA_LONG)
        ma_bullish = False
        if not ma_short.dropna().empty and not ma_long.dropna().empty:
            ma_bullish = ma_short.iloc[-1] > ma_long.iloc[-1]

        # 강세 점수 계산
        score = 0
        notes = []

        # 주간 수익률
        if weekly_chg > 5:
            score += 3
            notes.append(f"🔥 주간 {weekly_chg:+.1f}% 급등")
        elif weekly_chg > 2:
            score += 2
            notes.append(f"📈 주간 {weekly_chg:+.1f}% 상승")
        elif weekly_chg > 0:
            score += 1
            notes.append(f"주간 {weekly_chg:+.1f}% 소폭 상승")
        elif weekly_chg > -2:
            notes.append(f"주간 {weekly_chg:+.1f}% 소폭 하락")
        else:
            score -= 1
            notes.append(f"📉 주간 {weekly_chg:+.1f}% 하락")

        # 거래량 트렌드
        if vol_ratio > 2.0:
            score += 2
            notes.append(f"거래량 {vol_ratio:.1f}배 급증 (관심 집중)")
        elif vol_ratio > 1.5:
            score += 1
            notes.append(f"거래량 {vol_ratio:.1f}배 증가")

        # 상승일 비율
        if up_days >= 4:
            score += 2
            notes.append(f"주간 {up_days}일 상승 (강한 추세)")
        elif up_days >= 3:
            score += 1
            notes.append(f"주간 {up_days}일 상승")

        # RSI 반등 시그널
        if curr_rsi < 30:
            score += 2
            notes.append(f"RSI {curr_rsi:.0f} 과매도 (반등 기대)")
        elif curr_rsi < 40:
            score += 1
            notes.append(f"RSI {curr_rsi:.0f} 저평가권")

        # MACD 상승 모멘텀
        if macd_trend == "상승 모멘텀":
            score += 1
            notes.append("MACD 상승 모멘텀")

        # MA 정배열
        if ma_bullish:
            score += 1
            notes.append("이동평균 정배열 (상승추세)")

        last_close = float(close.iloc[-1])

        return {
            "ticker": ticker,
            "name": name,
            "market": market,
            "score": score,
            "weekly_change": weekly_chg,
            "last_close": last_close,
            "vol_ratio": vol_ratio,
            "up_days": up_days,
            "down_days": down_days,
            "rsi": curr_rsi,
            "notes": notes,
        }
    except Exception as e:
        print(f"  ❌ [{market} {ticker}] 주간 분석 오류: {e}")
        return None


def run_weekly_analysis(cfg, market: str | None = None) -> list[dict]:
    """월요일 주간 분석 실행."""
    targets = []
    if market is None or market == "kr":
        targets += [(t, name, "KR") for t, name in cfg.KR_TICKERS.items()]
    if market is None or market == "us":
        targets += [(t, name, "US") for t, name in cfg.US_TICKERS.items()]
        # 급등 스크리너 종목도 포함 (ETF 제외)
        existing = {t for t, _, _ in targets}
        for t in cfg.SURGE_UNIVERSE:
            if t not in existing and t not in ("SPY", "QQQ", "IWM"):
                targets.append((t, t, "US"))

    results = []
    for ticker, name, mkt in targets:
        r = analyze_weekly(ticker, name, mkt, cfg)
        if r:
            results.append(r)
            verdict = "🔥" if r["score"] >= 5 else "📈" if r["score"] >= 3 else "  "
            print(f"  {verdict} [{mkt} {ticker:6s}] 주간 {r['weekly_change']:+.1f}%  점수={r['score']:+d}")

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def format_weekly_report(date_str: str, results: list[dict], market: str, top_n: int = 10) -> str:
    """주간 분석 카카오톡 메시지 포맷."""
    flag = "🇰🇷" if market == "kr" else "🇺🇸"
    top = results[:top_n]

    if not top:
        return f"📅 {date_str} {flag} 주간 리뷰\n\n분석 가능한 종목이 없습니다."

    lines = [f"📅 {date_str} {flag} 주간 리뷰 + 금주 강세 예상"]
    lines.append("")
    lines.append("【지난주 흐름 기반 강세 TOP】")
    lines.append("")

    for i, r in enumerate(top, 1):
        medal = "🥇🥈🥉"[i - 1] if i <= 3 else f"{i}."
        price_fmt = f"${r['last_close']:,.2f}" if r["market"] == "US" else f"{r['last_close']:,.0f}"
        lines.append(f"{medal} {r['name']} ({r['ticker']})  점수 {r['score']:+d}")
        lines.append(f"   종가 {price_fmt} | 주간 {r['weekly_change']:+.1f}%")
        lines.append(f"   상승 {r['up_days']}일 / 하락 {r['down_days']}일")
        for note in r["notes"][:3]:
            lines.append(f"   • {note}")
        lines.append("")

    lines.append("⚠️ 교육용 참고 자료이며 투자 권유가 아닙니다.")
    return "\n".join(lines)
