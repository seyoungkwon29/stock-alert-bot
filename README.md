# 📈 Stock Alert Bot (KakaoTalk)

한국·미국 주식을 기술적 지표로 분석하고 **카카오톡 '나에게 메시지'** 로 매일 알림을 보내주는 초보용 퀀트 연습 프로젝트입니다.

> ⚠️ 이 프로젝트는 학습·연습용이며 투자 자문이 아닙니다. 실제 매매에 사용하지 마세요.

## 프로젝트 구조

```
trading/
├── config.py            # 종목 리스트, 지표 파라미터, 임계값
├── data_fetcher.py      # 한국(FinanceDataReader) / 미국(yfinance) 데이터 수집
├── indicators.py        # SMA, RSI, 볼린저밴드, MACD 계산
├── signals.py           # 각 지표를 +2~-2 점수로 환산 → 종합 점수
├── kakao_notifier.py    # 카카오 memo API 호출 + 자동 토큰 갱신
├── get_kakao_token.py   # OAuth 토큰 1회 발급 헬퍼 (로컬 서버)
├── main.py              # 실행 진입점
├── requirements.txt
└── .env.example         # 환경변수 템플릿
```

## 어떻게 작동하나요?

각 종목에 대해 네 가지 기술적 지표로 신호를 만들고, 이를 +2/+1/0/-1/-2 로 점수화한 뒤 합산합니다.

| 지표 | +2 (강한 상승) | -2 (강한 하락) |
|---|---|---|
| MA 크로스 | 골든크로스 (단기↗장기) | 데드크로스 (단기↘장기) |
| RSI | 과매도(<30) | 과매수(>70) |
| 볼린저밴드 | 하단 이탈(%B<0) | 상단 이탈(%B>1) |
| MACD | 히스토그램 상향전환 | 히스토그램 하향전환 |

종합 점수가 `+2` 이상이면 📈, `-2` 이하면 📉 알림이 카톡으로 발송됩니다. 임계값은 `config.py` 에서 조정할 수 있습니다.

---

## 🚀 빠른 시작 (총 15분)

### 1. 파이썬 패키지 설치

```bash
cd ~/Desktop/trading
pip install -r requirements.txt
```

Python 3.10 이상 권장. 가상환경을 쓰시려면:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 카카오 개발자 앱 만들기

**(1) 앱 생성**

1. [https://developers.kakao.com](https://developers.kakao.com) 접속 → 우상단 **로그인**
2. 상단 메뉴 **내 애플리케이션 > 애플리케이션 추가하기**
3. 앱 이름(예: `주식알림봇`), 사업자명(개인이면 본인 이름) 입력 → **저장**

**(2) 플랫폼 등록**

1. 만든 앱 클릭 → 좌측 **앱 설정 > 플랫폼**
2. **Web 플랫폼 등록** → 사이트 도메인에 `http://localhost:8080` 입력 → 저장

**(3) 카카오 로그인 활성화**

1. 좌측 **제품 설정 > 카카오 로그인**
2. **활성화 설정** 을 ON 으로 변경
3. 스크롤 → **Redirect URI 등록** 에 `http://localhost:8080/callback` 추가 → 저장

**(4) 동의항목 설정**

1. 좌측 **제품 설정 > 카카오 로그인 > 동의항목**
2. **카카오톡 메시지 전송** 항목의 상태를 **사용함** 으로 변경
   - "OpenID Connect 활성화 없이도 talk_message scope 는 본인 전용 메시지에 대해 바로 사용 가능" 안내가 보이면 그대로 저장
3. (앱 상태가 '개발' 이어도 본인 계정에는 메시지 전송이 됩니다.)

**(5) REST API 키 복사**

1. 좌측 **앱 설정 > 요약 정보** 또는 상단 앱 이름 옆
2. **REST API 키** 값을 복사

### 3. `.env` 파일 만들기

```bash
cp .env.example .env
```

`.env` 를 열어 `KAKAO_REST_API_KEY` 자리에 방금 복사한 값을 붙여넣어요.

```
KAKAO_REST_API_KEY=여기에_붙여넣기
KAKAO_REDIRECT_URI=http://localhost:8080/callback
KAKAO_ACCESS_TOKEN=
KAKAO_REFRESH_TOKEN=
```

### 4. 액세스 토큰 발급 (한 번만)

```bash
python get_kakao_token.py
```

그러면:

1. 터미널이 로컬 서버를 띄우고 브라우저를 자동으로 열어요
2. 카카오 로그인 + 권한 동의 진행 (본인 계정)
3. 동의 후 자동으로 `.env` 의 `KAKAO_ACCESS_TOKEN` / `KAKAO_REFRESH_TOKEN` 에 값이 채워져요

✅ 이제 준비 완료!

### 5. 카카오 알림 테스트

더미 메시지를 본인 카카오톡으로 보내봅니다:

```bash
python main.py --test
```

카카오톡의 **"나에게 보내기"** 채팅방을 확인해보세요 📬

### 6. 실제 분석 실행

```bash
# 임계값 넘는 종목만 알림
python main.py

# 전체 결과 알림 (첫 실전 테스트에 유용)
python main.py --all

# 전송 없이 콘솔 출력만
python main.py --dry-run
```

---

## ⏰ 매일 자동 실행 (cron, macOS/Linux)

장 마감 후에 자동으로 실행되게 하려면 `crontab -e` 에 아래 한 줄 추가:

```
# 평일 밤 10시
0 22 * * 1-5 cd ~/Desktop/trading && /usr/bin/python3 main.py >> run.log 2>&1
```

- Mac은 `/usr/bin/python3` 대신 `which python3` 결과 경로를 쓰세요.
- 노트북이 꺼져 있으면 실행되지 않습니다. 24시간 돌릴 서버가 없다면:
  - GitHub Actions `schedule` 트리거 (무료, `.env` 는 Secrets로)
  - Raspberry Pi / 클라우드 VM (AWS EC2 free tier, Oracle Cloud free)

## 🔑 토큰 만료와 자동 갱신

- `access_token` 은 약 **6시간** 유효
- `refresh_token` 은 약 **2개월** 유효
- 코드가 401을 받으면 자동으로 `refresh_token` 으로 갱신하고 `.env` 에 다시 저장합니다.
- 따라서 2개월 안에 한 번이라도 스크립트가 돌면 사실상 영구 동작.

**주의:** `.env` 파일은 절대 깃에 올리지 마세요. `.gitignore` 에 `.env` 추가 권장.

## 커스터마이징 아이디어

- `config.py` 의 `KR_TICKERS`, `US_TICKERS` 를 관심 종목으로 교체
- `SCORE_THRESHOLD_BUY/SELL` 조정해 알림 빈도 변경
- `signals.py` 에 거래량 급증, 이격도, OBV 등 지표 추가
- 결과를 CSV/DB에 저장하고 나중에 성과 백테스트

## 다음 학습 단계

1. **백테스트** (`backtrader`, `vectorbt`) — 이 신호로 과거에 매매했다면 수익률이 어땠는지
2. **팩터 모델** — Value/Momentum/Quality 스코어 조합
3. **포트폴리오 최적화** (`cvxpy`, `PyPortfolioOpt`) — 신호 + 비중까지
4. **리스크 관리** — 변동성 타겟팅, 손절 룰, 최대낙폭 제한

즐겁게 만들어보세요! 🚀
