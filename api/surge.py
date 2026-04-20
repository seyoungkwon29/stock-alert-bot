"""
Vercel 서버리스 API — 실시간 급등주 분석
---------------------------------------
GET /api/surge
→ 프리마켓/본장 실시간 데이터로 급등주 TOP 10 반환

응답 JSON:
{
  "timestamp": "2026-04-20 19:30 KST",
  "surging_now": [...],     // 지금 급등 중 TOP 10
  "predicted": [...]        // 장 마감 전 급등 예상 TOP 10
}
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler

# Vercel 서버리스에서 프로젝트 루트 접근
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import yfinance as yf

KST = timezone(timedelta(hours=9))

# 변동성 높은 상위 30개 종목 (빠른 분석용)
QUICK_UNIVERSE = [
    "TSLA", "NVDA", "AMD", "AAPL", "AMZN", "META", "MSFT", "GOOGL",
    "COIN", "PLTR", "SOFI", "HOOD", "RIVN", "LCID", "IONQ",
    "MARA", "RIOT", "UPST", "AFRM", "PATH",
    "SMCI", "MRNA", "ENPH", "GME", "AMC",
    "SNOW", "CRSP", "EDIT", "RKLB", "DXCM",
]


def _fetch_realtime(tickers: list[str]) -> list[dict]:
    """실시간 시세 + 장중 데이터 수집."""
    results = []
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            info = tk.info or {}

            # 현재가 (프리마켓 or 정규장)
            price = (
                info.get("preMarketPrice")
                or info.get("regularMarketPrice")
                or info.get("currentPrice")
            )
            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
            if not price or not prev_close:
                continue

            change_pct = (price / prev_close - 1) * 100

            # 거래량
            pre_vol = info.get("preMarketVolume") or 0
            reg_vol = info.get("regularMarketVolume") or 0
            curr_vol = reg_vol if reg_vol > 0 else pre_vol
            avg_vol = info.get("averageDailyVolume10Day") or info.get("averageVolume") or 1
            vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 0

            # 공매도
            short_pct = info.get("shortPercentOfFloat", 0) or 0
            if short_pct < 1:
                short_pct *= 100

            # 52주 범위
            w52_low = info.get("fiftyTwoWeekLow", 0) or 0
            w52_high = info.get("fiftyTwoWeekHigh", 0) or 0
            w52_pos = (price - w52_low) / (w52_high - w52_low) if w52_high > w52_low else 0.5

            results.append({
                "ticker": t,
                "name": info.get("shortName", t),
                "price": round(float(price), 2),
                "prev_close": round(float(prev_close), 2),
                "change_pct": round(change_pct, 2),
                "vol_ratio": round(vol_ratio, 2),
                "short_pct": round(short_pct, 1),
                "w52_pos": round(w52_pos, 2),
            })
        except Exception:
            pass
    return results


def _score_surging(items: list[dict]) -> list[dict]:
    """'지금 급등 중' 점수 — 현재 등락률 + 거래량 위주."""
    for item in items:
        score = 0
        notes = []

        chg = item["change_pct"]
        if chg > 5:
            score += 5
            notes.append(f"🔥 {chg:+.1f}% 급등 중")
        elif chg > 3:
            score += 4
            notes.append(f"📈 {chg:+.1f}% 강세")
        elif chg > 1:
            score += 2
            notes.append(f"{chg:+.1f}% 상승")
        elif chg > 0:
            score += 1
            notes.append(f"{chg:+.1f}%")
        else:
            notes.append(f"{chg:+.1f}%")

        vr = item["vol_ratio"]
        if vr > 3:
            score += 3
            notes.append(f"거래량 {vr:.1f}배 폭증")
        elif vr > 1.5:
            score += 2
            notes.append(f"거래량 {vr:.1f}배")
        elif vr > 0.5:
            score += 1

        sp = item["short_pct"]
        if sp >= 20:
            score += 2
            notes.append(f"공매도 {sp:.0f}%")
        elif sp >= 10:
            score += 1

        item["score"] = score
        item["notes"] = notes

    items.sort(key=lambda x: x["score"], reverse=True)
    return items[:10]


def _score_predicted(items: list[dict]) -> list[dict]:
    """'장 마감 전 급등 예상' — 모멘텀 + 스퀴즈 가능성 위주."""
    for item in items:
        score = 0
        notes = []

        chg = item["change_pct"]
        vr = item["vol_ratio"]
        sp = item["short_pct"]
        w52 = item["w52_pos"]

        # 상승 중 + 거래량 동반 = 추가 상승 가능성
        if chg > 0 and vr > 1:
            score += 3
            notes.append(f"상승({chg:+.1f}%) + 거래량({vr:.1f}x) 동반")
        elif chg > 0:
            score += 1
            notes.append(f"상승 중 ({chg:+.1f}%)")

        # 공매도 비율 높으면 스퀴즈 가능
        if sp >= 20 and chg > 0:
            score += 4
            notes.append(f"🔥 숏스퀴즈 가능 (공매도 {sp:.0f}% + 상승)")
        elif sp >= 20:
            score += 2
            notes.append(f"공매도 {sp:.0f}% (스퀴즈 대기)")
        elif sp >= 10:
            score += 1

        # 거래량 급증 = 세력 유입
        if vr > 3:
            score += 3
            notes.append(f"거래량 {vr:.1f}배 (세력 유입 가능)")
        elif vr > 2:
            score += 2

        # 52주 저점 근처에서 반등
        if w52 < 0.2 and chg > 0:
            score += 2
            notes.append(f"52주 저점권({w52:.0%})에서 반등")

        # 소폭 하락이지만 거래량 급증 = 바닥 다지기
        if -2 < chg < 0 and vr > 2:
            score += 2
            notes.append(f"소폭 조정 + 거래량 급증 (바닥 다지기)")

        item["pred_score"] = score
        item["pred_notes"] = notes

    items.sort(key=lambda x: x["pred_score"], reverse=True)
    return items[:10]


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            now = datetime.now(KST)
            timestamp = now.strftime("%Y-%m-%d %H:%M KST")

            raw = _fetch_realtime(QUICK_UNIVERSE)

            surging = _score_surging([dict(r) for r in raw])
            predicted = _score_predicted([dict(r) for r in raw])

            body = json.dumps({
                "timestamp": timestamp,
                "surging_now": surging,
                "predicted": predicted,
            }, ensure_ascii=False)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "public, max-age=30")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()
