"""
카카오톡 '나에게 메시지 보내기' 알림 모듈
-----------------------------------------
- Kakao REST API의 memo/default/send 엔드포인트 사용
- 액세스 토큰 만료(401) 시 refresh_token으로 자동 재발급
- 갱신된 토큰은 .env 파일에 덮어써 다음 실행 때 재활용

필요한 환경변수 (.env):
    KAKAO_REST_API_KEY    (카카오 앱 REST API 키)
    KAKAO_ACCESS_TOKEN    (get_kakao_token.py 로 1회 발급)
    KAKAO_REFRESH_TOKEN   (동시에 발급됨, 2개월 유효)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


# -------------------------------------------------------------
# .env 유틸
# -------------------------------------------------------------
def _update_env_file(updates: dict, env_path: str = ".env") -> None:
    """.env 파일에서 지정된 키 값을 교체(없으면 추가)."""
    path = Path(env_path)
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    new_lines, replaced = [], set()
    for line in lines:
        k = line.split("=", 1)[0].strip() if "=" in line else ""
        if k in updates:
            new_lines.append(f"{k}={updates[k]}")
            replaced.add(k)
        else:
            new_lines.append(line)
    for k, v in updates.items():
        if k not in replaced:
            new_lines.append(f"{k}={v}")
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


# -------------------------------------------------------------
# 토큰 갱신
# -------------------------------------------------------------
def refresh_access_token() -> str | None:
    """refresh_token으로 access_token 재발급. 새 토큰을 env에 반영."""
    rest_key = os.getenv("KAKAO_REST_API_KEY")
    refresh_token = os.getenv("KAKAO_REFRESH_TOKEN")
    if not (rest_key and refresh_token):
        print("[kakao] REST_API_KEY 또는 REFRESH_TOKEN 미설정.")
        return None

    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "client_id": rest_key,
        "refresh_token": refresh_token,
    }).encode()

    req = urllib.request.Request(
        KAKAO_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
    except Exception as e:
        print(f"[kakao] 토큰 갱신 실패: {e}")
        return None

    new_access = body.get("access_token")
    new_refresh = body.get("refresh_token")

    updates = {}
    if new_access:
        os.environ["KAKAO_ACCESS_TOKEN"] = new_access
        updates["KAKAO_ACCESS_TOKEN"] = new_access
    if new_refresh:  # 카카오는 갱신 시 refresh_token도 가끔 재발급
        os.environ["KAKAO_REFRESH_TOKEN"] = new_refresh
        updates["KAKAO_REFRESH_TOKEN"] = new_refresh
    if updates:
        _update_env_file(updates)
    return new_access


# -------------------------------------------------------------
# 실제 메시지 전송
# -------------------------------------------------------------
def _send(text: str, access_token: str) -> tuple[bool, int]:
    """memo API 호출. (성공 여부, HTTP 코드) 반환."""
    template = {
        "object_type": "text",
        "text": text[:3900],  # 카카오는 4000자 제한
        "link": {},
    }
    data = urllib.parse.urlencode({
        "template_object": json.dumps(template, ensure_ascii=False),
    }).encode()

    req = urllib.request.Request(
        KAKAO_MEMO_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200, resp.status
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            print(f"[kakao] {e.code} {err}")
        except Exception:
            print(f"[kakao] HTTP {e.code}")
        return False, e.code
    except Exception as e:
        print(f"[kakao] 전송 오류: {e}")
        return False, 0


def send_kakao(message: str) -> bool:
    """카카오 '나에게' 메시지 전송. 토큰 만료 시 1회 자동 갱신 후 재시도."""
    token = os.getenv("KAKAO_ACCESS_TOKEN")
    if not token:
        print("[kakao] KAKAO_ACCESS_TOKEN 미설정. 콘솔에 메시지만 출력합니다.\n")
        print(message)
        return False

    ok, code = _send(message, token)
    if ok:
        return True

    # 토큰 만료 → 갱신 후 재시도
    if code == 401:
        print("[kakao] 액세스 토큰 만료, 자동 갱신 시도...")
        new_token = refresh_access_token()
        if new_token:
            ok, _ = _send(message, new_token)
            if ok:
                print("[kakao] 갱신 후 전송 성공")
            return ok

    return False


# -------------------------------------------------------------
# 메시지 포맷팅 (카카오는 HTML 미지원 → plain text)
# -------------------------------------------------------------
def format_report(date_str: str, alerts: list) -> str:
    if not alerts:
        return f"📊 {date_str} 종목 분석\n\n임계값을 넘는 신호가 없습니다."

    lines = [f"📊 {date_str} 종목 신호 리포트"]
    for a in alerts:
        flag = "🇰🇷" if a["market"] == "KR" else "🇺🇸"
        lines.append("")
        lines.append(
            f"{flag} {a['name']} ({a['ticker']}) → {a['verdict']} (점수 {a['score']:+d})"
        )
        lines.append(f"  종가 {a['last_close']:,.2f} ({a['change_pct']:+.2f}%)")
        for note in a["notes"]:
            lines.append(f"  • {note}")
    lines.append("")
    lines.append("⚠️ 교육용 참고 자료이며 투자 권유가 아닙니다.")
    return "\n".join(lines)
