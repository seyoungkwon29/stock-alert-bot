"""
설정 파일
----------
분석할 종목, 기간, 점수 임계값 등을 이곳에서 관리합니다.
텔레그램 봇 토큰 등 민감 정보는 .env 파일에 보관하세요.
"""

# -----------------------------
# 분석할 종목 리스트
# -----------------------------
# 한국 종목: 6자리 티커 (예: 삼성전자 = "005930")
KR_TICKERS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "035420": "NAVER",
    "035720": "카카오",
    "051910": "LG화학",
}

# 미국 종목: 티커 심볼 (예: 애플 = "AAPL")
US_TICKERS = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "GOOGL": "Alphabet",
    "TSLA": "Tesla",
}

# -----------------------------
# 데이터 수집 기간 (일)
# -----------------------------
# 지표 계산을 위해 최소 200일 이상 권장 (MA200 계산용)
LOOKBACK_DAYS = 300

# -----------------------------
# 기술적 지표 파라미터
# -----------------------------
MA_SHORT = 20            # 단기 이동평균
MA_LONG = 60             # 장기 이동평균
RSI_PERIOD = 14          # RSI 기간
RSI_OVERSOLD = 30        # 과매도 기준
RSI_OVERBOUGHT = 70      # 과매수 기준
BB_PERIOD = 20           # 볼린저밴드 기간
BB_STD = 2.0             # 볼린저밴드 표준편차
MACD_FAST = 12           # MACD 단기
MACD_SLOW = 26           # MACD 장기
MACD_SIGNAL = 9          # MACD 시그널

# -----------------------------
# 알림 임계값
# -----------------------------
# 종합 점수가 아래 값 이상이면 '상승 신호'로 알림
SCORE_THRESHOLD_BUY = 2
# 종합 점수가 아래 값 이하이면 '하락 신호'로 알림
SCORE_THRESHOLD_SELL = -2

# -----------------------------
# 급등 후보 스크리너 설정
# -----------------------------
# 스캔 대상 미국 종목 (유동성 높은 종목 위주)
SURGE_UNIVERSE = [
    # 대형 기술주
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "INTC", "CRM",
    "NFLX", "ADBE", "PYPL", "SHOP", "SNOW", "PLTR", "UBER", "COIN", "ROKU",
    # 반도체
    "AVGO", "QCOM", "MU", "MRVL", "ON", "SMCI",
    # 바이오/헬스케어
    "MRNA", "BNTX", "CRSP", "EDIT", "DXCM", "ISRG",
    # 에너지/자원
    "XOM", "CVX", "OXY", "FSLR", "ENPH", "RIG",
    # 금융
    "JPM", "GS", "BAC", "C", "SOFI", "HOOD",
    # 소비재/리테일
    "NKE", "SBUX", "DIS", "ABNB", "RIVN", "LCID",
    # 산업/기타
    "BA", "CAT", "DE", "LMT", "RTX",
    # 중소형 고변동성
    "GME", "AMC", "BBBY", "MARA", "RIOT", "AFRM", "UPST", "PATH", "IONQ", "RKLB",
    # ETF (시장 전체 방향 참고)
    "SPY", "QQQ", "IWM",
]

# 급등 스크리너 파라미터
SURGE_VOL_RATIO_STRONG = 3.0    # 거래량 3배 이상 → 강한 신호
SURGE_VOL_RATIO_MID = 2.0       # 거래량 2배 이상 → 중간 신호
SURGE_VOL_RATIO_WEAK = 1.5      # 거래량 1.5배 이상 → 약한 신호
SURGE_SHORT_HIGH = 20.0         # 공매도 비율 20% 이상 → 스퀴즈 후보
SURGE_SHORT_MID = 10.0          # 공매도 비율 10% 이상
SURGE_CONSEC_DOWN_DAYS = 3      # 연속 하락일 수 (평균회귀 신호)
SURGE_TOP_N = 10                # 상위 N개 종목만 알림
