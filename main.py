"""
메인 실행 스크립트
------------------
1. config.py 에 정의된 한국/미국 종목 데이터 수집
2. 지표 계산 및 신호 분석
3. 임계값을 넘는 종목만 카카오톡 '나에게' 로 알림 전송

실행:
    python main.py                # 임계값 통과 종목만 알림
    python main.py --all          # 전체 종목 결과 알림
    python main.py --market kr    # 한국 종목만
    python main.py --market us    # 미국 종목만 + 급등 후보
    python main.py --dry-run      # 콘솔 출력만 (전송 안 함)
    python main.py --test         # 더미 메시지로 카카오 전송 테스트
    python main.py --surge        # 급등 후보 스크리너만
"""

import argparse
import sys
import traceback
from datetime import datetime

from dotenv import load_dotenv

import config
from data_fetcher import fetch
from indicators import compute_all
from signals import analyze
from kakao_notifier import send_kakao, format_report
from surge_screener import run_surge_screen, format_surge_report


def run(send_all: bool = False, dry_run: bool = False, market: str | None = None) -> int:
    load_dotenv()
    today = datetime.now().strftime("%Y-%m-%d")

    targets = []
    if market is None or market == "kr":
        targets += [(t, name, "KR") for t, name in config.KR_TICKERS.items()]
    if market is None or market == "us":
        targets += [(t, name, "US") for t, name in config.US_TICKERS.items()]

    alerts = []
    for ticker, name, mkt in targets:
        try:
            df = fetch(ticker, mkt, config.LOOKBACK_DAYS)
            if df.empty or len(df) < max(config.MA_LONG, config.BB_PERIOD) + 5:
                print(f"[{mkt} {ticker} {name}] 데이터 부족, 건너뜀")
                continue

            df = compute_all(df, config)
            result = analyze(df, config)
            result.update({"ticker": ticker, "name": name, "market": mkt})

            print(
                f"[{mkt} {ticker} {name}] "
                f"score={result['score']:+d}  {result['verdict']}  "
                f"close={result['last_close']:.2f} ({result['change_pct']:+.2f}%)"
            )

            if send_all:
                alerts.append(result)
            elif (
                result["score"] >= config.SCORE_THRESHOLD_BUY
                or result["score"] <= config.SCORE_THRESHOLD_SELL
            ):
                alerts.append(result)

        except Exception as e:
            print(f"[{mkt} {ticker} {name}] 오류: {e}")
            traceback.print_exc()

    alerts.sort(key=lambda x: abs(x["score"]), reverse=True)

    # 미국 시장인 경우 급등 후보 스크리너도 함께 실행
    surge_msg = ""
    if market == "us" or market is None:
        print(f"\n{'='*60}")
        print("급등 후보 스크리너 실행 중...\n")
        surge_results = run_surge_screen(config)
        surge_msg = "\n\n" + format_surge_report(today, surge_results)

    message = format_report(today, alerts) + surge_msg
    print("\n" + "=" * 60)
    print(message)
    print("=" * 60 + "\n")

    if dry_run:
        print("[dry-run] 카카오 전송 생략")
        return 0

    ok = send_kakao(message)
    print("✅ 전송 성공" if ok else "❌ 전송 실패")
    return 0 if ok or not alerts else 1


def test_kakao() -> int:
    """더미 데이터로 카카오 연결 확인."""
    load_dotenv()
    sample = [{
        "ticker": "005930", "name": "삼성전자", "market": "KR",
        "verdict": "📈 상승 신호", "score": 3,
        "last_close": 75000.0, "change_pct": 1.23,
        "notes": [
            "🟢 골든크로스 (MA20↗MA60)",
            "RSI 32.5 (과매도, 반등 가능)",
            "하단 근접 (%B=0.15)",
            "🟢 MACD 상향전환",
        ],
    }]
    today = datetime.now().strftime("%Y-%m-%d")
    msg = format_report(today, sample)
    print(msg)
    print()
    ok = send_kakao(msg)
    print("✅ 전송 성공" if ok else "❌ 전송 실패")
    return 0 if ok else 1


def run_surge(dry_run: bool = False, top_n: int | None = None) -> int:
    """급등 후보 스크리너 실행."""
    load_dotenv()
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"🔍 {today} 급등 후보 스크리너 시작\n")
    results = run_surge_screen(config, top_n)

    message = format_surge_report(today, results)
    print("\n" + "=" * 60)
    print(message)
    print("=" * 60 + "\n")

    if dry_run:
        print("[dry-run] 카카오 전송 생략")
        return 0

    ok = send_kakao(message)
    print("✅ 전송 성공" if ok else "❌ 전송 실패")
    return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="임계값과 관계없이 전체 결과 전송")
    parser.add_argument("--dry-run", action="store_true", help="전송 없이 콘솔만")
    parser.add_argument("--test", action="store_true", help="더미 메시지로 카카오 테스트")
    parser.add_argument("--surge", action="store_true", help="급등 후보 스크리너만")
    parser.add_argument("--top", type=int, default=None, help="급등 후보 상위 N개 (기본 10)")
    parser.add_argument("--market", choices=["kr", "us"], help="한국(kr) 또는 미국(us) 종목만")
    args = parser.parse_args()
    if args.test:
        sys.exit(test_kakao())
    if args.surge:
        sys.exit(run_surge(dry_run=args.dry_run, top_n=args.top))
    sys.exit(run(send_all=args.all, dry_run=args.dry_run, market=args.market))
