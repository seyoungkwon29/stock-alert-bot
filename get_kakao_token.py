"""
카카오 OAuth 토큰 발급 헬퍼 (1회 실행용)
-----------------------------------------
사전 조건:
  1) https://developers.kakao.com 에서 앱 생성
  2) 앱 설정 > 플랫폼 > Web 추가: http://localhost:8080
  3) 카카오 로그인 > 활성화 ON, Redirect URI: http://localhost:8080/callback
  4) 카카오 로그인 > 동의항목 > '카카오톡 메시지 전송' (talk_message) 활성화
  5) 요약정보 탭의 'REST API 키' 를 .env 의 KAKAO_REST_API_KEY 에 입력

실행:
    python get_kakao_token.py

동작:
  - 브라우저가 자동으로 열리며 카카오 로그인 + 동의 진행
  - 로컬 서버가 콜백을 받아 code → 토큰 교환
  - access / refresh 토큰이 터미널에 출력 + .env 에 자동 저장
"""

import http.server
import json
import os
import socketserver
import threading
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

from kakao_notifier import _update_env_file  # 재사용

load_dotenv()

REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "").strip()
REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI", "http://localhost:8080/callback").strip()

# 포트 추출
try:
    PORT = int(REDIRECT_URI.split(":")[2].split("/")[0])
except Exception:
    PORT = 8080

_auth_code: dict = {"code": None, "error": None}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        if "code" in params:
            _auth_code["code"] = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "<h2>✅ 인증 완료!</h2><p>터미널로 돌아가 주세요.</p>".encode("utf-8")
            )
        elif "error" in params:
            _auth_code["error"] = params.get("error_description", ["unknown"])[0]
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"<h2>에러: {_auth_code['error']}</h2>".encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args, **kwargs):  # 조용히
        pass


def main() -> int:
    if not REST_API_KEY:
        print("❌ .env 에 KAKAO_REST_API_KEY 가 없습니다.")
        print("   developers.kakao.com → 내 앱 → 요약정보 → 'REST API 키' 복사")
        return 1

    auth_url = (
        "https://kauth.kakao.com/oauth/authorize?"
        + urllib.parse.urlencode({
            "response_type": "code",
            "client_id": REST_API_KEY,
            "redirect_uri": REDIRECT_URI,
            "scope": "talk_message",
        })
    )

    print(f"🌐 포트 {PORT} 에서 콜백 대기 중...")
    httpd = socketserver.TCPServer(("localhost", PORT), _CallbackHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    print(f"🔗 브라우저를 엽니다: {auth_url}\n")
    webbrowser.open(auth_url)

    # 콜백 대기
    import time
    for _ in range(180):  # 3분 타임아웃
        if _auth_code["code"] or _auth_code["error"]:
            break
        time.sleep(1)

    httpd.shutdown()

    if _auth_code["error"]:
        print(f"❌ 동의 실패: {_auth_code['error']}")
        return 1
    if not _auth_code["code"]:
        print("❌ 3분 내에 인증이 완료되지 않았습니다.")
        return 1

    # 토큰 교환
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": REST_API_KEY,
        "redirect_uri": REDIRECT_URI,
        "code": _auth_code["code"],
    }).encode()

    req = urllib.request.Request(
        "https://kauth.kakao.com/oauth/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            tokens = json.loads(resp.read().decode())
    except Exception as e:
        print(f"❌ 토큰 교환 실패: {e}")
        return 1

    access = tokens.get("access_token")
    refresh = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in")
    refresh_expires_in = tokens.get("refresh_token_expires_in")

    if not access:
        print(f"❌ 응답에 access_token 이 없습니다: {tokens}")
        return 1

    print("\n=== 🎉 토큰 발급 성공 ===")
    print(f"access_token  ({expires_in}초 유효): {access[:20]}...")
    if refresh:
        print(f"refresh_token ({refresh_expires_in}초 유효): {refresh[:20]}...")

    updates = {"KAKAO_ACCESS_TOKEN": access}
    if refresh:
        updates["KAKAO_REFRESH_TOKEN"] = refresh
    _update_env_file(updates)
    print("\n✅ .env 파일에 자동 저장되었습니다.")
    print("   이제 `python main.py --all` 로 알림을 보내보세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
