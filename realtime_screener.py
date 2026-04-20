"""
실시간 급등주 스크리너
----------------------
yfinance의 프리마켓/장중 데이터를 활용하여
급등 가능성이 높은 종목을 실시간으로 분석합니다.

분석 모드:
  - premarket: 프리마켓 데이터 (한국시간 오후 6~10시)
  - intraday:  본장 데이터 (한국시간 오후 10:30~)

⚠️ 교육/연습용이며 투자 자문이 아닙니다.
"""

from __future__ import annotations

import traceback
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

from indicators import rsi, macd, bollinger_bands


def _get_premarket_data(tickers: list[str]) -> list[dict]:
    """프리마켓 실시간 시세 수집."""
    results = []
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            info = tk.info or {}

            pre_price = info.get("preMarketPrice")
            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
            pre_change = info.get("preMarketChangePercent")

            if pre_price and prev_close:
                if not pre_change:
                    pre_change = (pre_price / prev_close - 1) * 100
                else:
                    pre_change = pre_change * 100 if abs(pre_change) < 1 else pre_change
            elif not pre_price:
                # 프리마켓 데이터 없으면 정규장 데이터 사용
                pre_price = info.get("regularMarketPrice") or info.get("currentPrice")
                if pre_price and prev_close:
                    pre_change = (pre_price / prev_close - 1) * 100
                else:
                    continue

            pre_volume = info.get("preMarketVolume") or 0
            avg_volume = info.get("averageDailyVolume10Day") or info.get("averageVolume") or 1
            vol_ratio = pre_volume / avg_volume * 10 if avg_volume > 0 else 0  # 프리마켓은 본장의 ~10%

            short_pct = info.get("shortPercentOfFloat", 0) or 0
            if short_pct < 1:
                short_pct *= 100

            results.append({
                "ticker": t,
                "name": info.get("shortName", t),
                "price": float(pre_price),
                "prev_close": float(prev_close) if prev_close else 0,
                "change_pct": float(pre_change) if pre_change else 0,
                "pre_volume": int(pre_volume),
                "vol_ratio": float(vol_ratio),
                "short_pct": float(short_pct),
                "market_cap": info.get("marketCap", 0) or 0,
            })
        except Exception:
            pass
    return results


def _get_intraday_data(tickers: list[str]) -> list[dict]:
    """본장 장중 데이터 수집 (5분봉)."""
    results = []
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            info = tk.info or {}

            # 5분봉 데이터 (프리마켓 포함)
            df = yf.download(t, period="1d", interval="5m", prepost=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if df.empty:
                continue

            curr_price = float(df["Close"].iloc[-1])
            open_price = float(df["Open"].iloc[0])
            high_price = float(df["High"].max())
            low_price = float(df["Low"].min())
            total_volume = int(df["Volume"].sum())

            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or open_price
            change_pct = (curr_price / prev_close - 1) * 100 if prev_close else 0
            intraday_range = (high_price - low_price) / low_price * 100 if low_price else 0

            avg_volume = info.get("averageDailyVolume10Day") or info.get("averageVolume") or 1
            vol_ratio = total_volume / avg_volume if avg_volume > 0 else 0

            short_pct = info.get("shortPercentOfFloat", 0) or 0
            if short_pct < 1:
                short_pct *= 100

            # 장중 모멘텀: 최근 30분 추세
            recent = df.tail(6)  # 최근 6봉 = 30분
            if len(recent) >= 2:
                momentum = (float(recent["Close"].iloc[-1]) / float(recent["Close"].iloc[0]) - 1) * 100
            else:
                momentum = 0

            results.append({
                "ticker": t,
                "name": info.get("shortName", t),
                "price": curr_price,
                "prev_close": float(prev_close),
                "change_pct": change_pct,
                "open_price": open_price,
                "high": high_price,
                "low": low_price,
                "volume": total_volume,
                "vol_ratio": vol_ratio,
                "intraday_range": intraday_range,
                "momentum_30m": momentum,
                "short_pct": short_pct,
            })
        except Exception:
            pass
    return results


def _score_premarket(item: dict, cfg) -> dict:
    """프리마켓 종목 점수 계산."""
    score = 0
    notes = []

    # 프리마켓 등락률
    chg = item["change_pct"]
    if chg > 5:
        score += 4
        notes.append(f"🔥 프리마켓 {chg:+.1f}% 급등")
    elif chg > 3:
        score += 3
        notes.append(f"📈 프리마켓 {chg:+.1f}% 강세")
    elif chg > 1:
        score += 2
        notes.append(f"프리마켓 {chg:+.1f}% 상승")
    elif chg > 0:
        score += 1
        notes.append(f"프리마켓 {chg:+.1f}%")

    # 프리마켓 거래량
    vr = item["vol_ratio"]
    if vr > 3:
        score += 3
        notes.append(f"🔥 프리마켓 거래량 폭증 ({vr:.1f}x)")
    elif vr > 1.5:
        score += 2
        notes.append(f"📊 프리마켓 거래량 활발 ({vr:.1f}x)")
    elif vr > 0.5:
        score += 1
        notes.append(f"프리마켓 거래량 양호")

    # 공매도 비율 (숏스퀴즈 가능성)
    sp = item["short_pct"]
    if sp >= 20:
        score += 3
        notes.append(f"🔥 공매도 {sp:.1f}% (스퀴즈 후보)")
    elif sp >= 10:
        score += 2
        notes.append(f"📊 공매도 {sp:.1f}%")
    elif sp >= 5:
        score += 1
        notes.append(f"공매도 {sp:.1f}%")

    item["score"] = score
    item["notes"] = notes
    return item


def _score_intraday(item: dict, cfg) -> dict:
    """본장 장중 종목 점수 계산."""
    score = 0
    notes = []

    # 당일 등락률
    chg = item["change_pct"]
    if chg > 5:
        score += 4
        notes.append(f"🔥 당일 {chg:+.1f}% 급등")
    elif chg > 3:
        score += 3
        notes.append(f"📈 당일 {chg:+.1f}% 강세")
    elif chg > 1:
        score += 2
        notes.append(f"당일 {chg:+.1f}% 상승")
    elif chg > 0:
        score += 1
        notes.append(f"당일 {chg:+.1f}%")

    # 거래량 비율
    vr = item["vol_ratio"]
    if vr > 2:
        score += 3
        notes.append(f"🔥 거래량 {vr:.1f}배 폭증")
    elif vr > 1:
        score += 2
        notes.append(f"📊 거래량 활발 ({vr:.1f}x)")
    elif vr > 0.5:
        score += 1

    # 30분 모멘텀
    mom = item["momentum_30m"]
    if mom > 2:
        score += 3
        notes.append(f"🚀 30분 모멘텀 {mom:+.1f}%")
    elif mom > 1:
        score += 2
        notes.append(f"📈 30분 모멘텀 {mom:+.1f}%")
    elif mom > 0.3:
        score += 1
        notes.append(f"모멘텀 상승 중 ({mom:+.1f}%)")

    # 장중 변동성
    rng = item["intraday_range"]
    if rng > 5:
        score += 1
        notes.append(f"변동성 높음 ({rng:.1f}%)")

    # 공매도 비율
    sp = item["short_pct"]
    if sp >= 20:
        score += 3
        notes.append(f"🔥 공매도 {sp:.1f}% (스퀴즈 가능)")
    elif sp >= 10:
        score += 2
        notes.append(f"📊 공매도 {sp:.1f}%")
    elif sp >= 5:
        score += 1

    item["score"] = score
    item["notes"] = notes
    return item


def run_realtime_screen(cfg, mode: str = "premarket", top_n: int = 10) -> list[dict]:
    """실시간 스크리너 실행.

    mode: "premarket" 또는 "intraday"
    """
    tickers = [t for t in cfg.SURGE_UNIVERSE if t not in ("SPY", "QQQ", "IWM")]
    label = "프리마켓" if mode == "premarket" else "본장"

    print(f"📡 {len(tickers)}개 종목 {label} 데이터 수집 중...")

    if mode == "premarket":
        raw = _get_premarket_data(tickers)
    else:
        raw = _get_intraday_data(tickers)

    print(f"   {len(raw)}개 종목 수집 완료\n")

    results = []
    for item in raw:
        try:
            if mode == "premarket":
                scored = _score_premarket(item, cfg)
            else:
                scored = _score_intraday(item, cfg)
            results.append(scored)

            verdict = "🔥" if scored["score"] >= 5 else "📈" if scored["score"] >= 3 else "  "
            print(f"  {verdict} [{scored['ticker']:6s}] {scored['name'][:20]:20s}  점수={scored['score']:+2d}  ${scored['price']:>10.2f} ({scored['change_pct']:+.1f}%)")
        except Exception as e:
            print(f"  ❌ [{item.get('ticker', '?')}] 오류: {e}")

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]


def format_realtime_report(date_str: str, results: list[dict], mode: str, timestamp: str = "") -> str:
    """실시간 스크리너 카카오톡 메시지 포맷."""
    label = "프리마켓" if mode == "premarket" else "본장"
    ts = f" ({timestamp})" if timestamp else ""

    if not results:
        return f"🔥 {date_str} {label} 급등주{ts}\n\n데이터 수집 중 또는 해당 종목 없음"

    lines = [f"🔥 {date_str} {label} 급등주 TOP {len(results)}{ts}"]
    lines.append("")

    for i, r in enumerate(results, 1):
        medal = "🥇🥈🥉"[i - 1] if i <= 3 else f"{i}."
        lines.append(f"{medal} {r['name']} ({r['ticker']})  점수 {r['score']:+d}")
        lines.append(f"   ${r['price']:,.2f} ({r['change_pct']:+.1f}%)")
        if r.get("short_pct", 0) > 0:
            lines.append(f"   공매도 {r['short_pct']:.1f}%")
        for note in r.get("notes", []):
            lines.append(f"   • {note}")
        lines.append("")

    lines.append("💡 자세히 보기 → 시간대별 순위 비교")
    lines.append("⚠️ 교육용 참고 자료이며 투자 권유가 아닙니다.")
    return "\n".join(lines)
