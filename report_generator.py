"""
HTML 리포트 생성 모듈
--------------------
분석 결과를 GitHub Pages에 배포할 HTML 파일로 생성합니다.
"""

from __future__ import annotations

import os
from pathlib import Path


PAGES_URL = "https://seyoungkwon29.github.io/stock-alert-bot"

TEMPLATE = """\
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, 'Pretendard', sans-serif; background: #0f0f0f; color: #e0e0e0; padding: 16px; max-width: 640px; margin: 0 auto; }}
  h1 {{ font-size: 1.3rem; margin-bottom: 16px; color: #fff; }}
  .timestamp {{ color: #888; font-size: 0.85rem; margin-bottom: 20px; }}
  .card {{ background: #1a1a1a; border-radius: 12px; padding: 16px; margin-bottom: 12px; border: 1px solid #2a2a2a; }}
  .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
  .ticker {{ font-weight: 700; font-size: 1.1rem; color: #fff; }}
  .score-pos {{ color: #22c55e; font-weight: 700; }}
  .score-neg {{ color: #ef4444; font-weight: 700; }}
  .score-neu {{ color: #888; font-weight: 700; }}
  .price {{ font-size: 0.95rem; color: #aaa; margin-bottom: 8px; }}
  .change-pos {{ color: #22c55e; }}
  .change-neg {{ color: #ef4444; }}
  .note {{ font-size: 0.85rem; color: #bbb; padding: 2px 0; }}
  .medal {{ font-size: 1.2rem; margin-right: 4px; }}
  .section {{ margin-top: 24px; margin-bottom: 12px; font-size: 1.1rem; font-weight: 700; color: #fff; border-bottom: 1px solid #333; padding-bottom: 8px; }}
  .short-badge {{ background: #7c3aed; color: #fff; font-size: 0.75rem; padding: 2px 8px; border-radius: 10px; }}
  .footer {{ text-align: center; color: #666; font-size: 0.8rem; margin-top: 24px; padding: 16px 0; border-top: 1px solid #222; }}
  .nav {{ display: flex; gap: 8px; margin-bottom: 16px; }}
  .nav a {{ color: #60a5fa; text-decoration: none; font-size: 0.9rem; padding: 6px 12px; border: 1px solid #333; border-radius: 8px; }}
  .nav a:hover {{ background: #1a1a2e; }}
  .darkfina {{ display: flex; gap: 6px; margin-top: 8px; }}
  .darkfina a {{ color: #a78bfa; text-decoration: none; font-size: 0.75rem; padding: 3px 8px; border: 1px solid #3a3a5a; border-radius: 6px; }}
  .darkfina a:hover {{ background: #2a2a4a; }}
</style>
</head>
<body>
<div class="nav">
  <a href="index.html">홈</a>
  <a href="kr.html">🇰🇷 한국</a>
  <a href="us.html">🇺🇸 미국</a>
</div>
<h1>{title}</h1>
<div class="timestamp">{timestamp}</div>
{content}
<div class="footer">⚠️ 교육용 참고 자료이며 투자 권유가 아닙니다.</div>
</body>
</html>
"""


def _change_class(pct: float) -> str:
    return "change-pos" if pct >= 0 else "change-neg"


def _score_class(score: int) -> str:
    if score >= 2:
        return "score-pos"
    if score <= -2:
        return "score-neg"
    return "score-neu"


def _darkfina_links(ticker: str, market: str) -> str:
    """미국 종목에 대해 DarkFina 바로가기 링크 생성."""
    if market != "US":
        return ""
    base = "https://darkfina.crazyrabbit.co"
    return f"""<div class="darkfina">
    <a href="{base}/darkpool/{ticker}" target="_blank">🌑 다크풀</a>
    <a href="{base}/short/{ticker}" target="_blank">📉 공매도</a>
  </div>"""


def _render_analysis_cards(alerts: list[dict]) -> str:
    """기술적 분석 결과 카드."""
    if not alerts:
        return '<div class="card"><p>임계값을 넘는 신호가 없습니다.</p></div>'
    html = ""
    for a in alerts:
        flag = "🇰🇷" if a["market"] == "KR" else "🇺🇸"
        notes_html = "".join(f'<div class="note">• {n}</div>' for n in a["notes"])
        darkfina = _darkfina_links(a["ticker"], a["market"])
        html += f"""
<div class="card">
  <div class="card-header">
    <span class="ticker">{flag} {a['name']} ({a['ticker']})</span>
    <span class="{_score_class(a['score'])}">{a['verdict']} ({a['score']:+d})</span>
  </div>
  <div class="price">종가 {a['last_close']:,.2f} <span class="{_change_class(a['change_pct'])}">({a['change_pct']:+.2f}%)</span></div>
  {notes_html}
  {darkfina}
</div>"""
    return html


def _render_surge_cards(results: list[dict]) -> str:
    """급등 후보 카드."""
    if not results:
        return '<div class="card"><p>조건을 충족하는 종목이 없습니다.</p></div>'
    medals = ["🥇", "🥈", "🥉"]
    html = ""
    for i, r in enumerate(results):
        medal = medals[i] if i < 3 else f"{i+1}."
        short_html = f'<span class="short-badge">공매도 {r["short_pct"]:.1f}%</span>' if r.get("short_pct", 0) > 0 else ""
        notes_html = "".join(f'<div class="note">• {n}</div>' for n in r["notes"])
        darkfina = _darkfina_links(r["ticker"], "US")
        html += f"""
<div class="card">
  <div class="card-header">
    <span class="ticker"><span class="medal">{medal}</span> {r['name']} ({r['ticker']})</span>
    <span class="score-pos">+{r['score']}</span>
  </div>
  <div class="price">종가 ${r['last_close']:,.2f} <span class="{_change_class(r['change_pct'])}">({r['change_pct']:+.1f}%)</span> {short_html}</div>
  {notes_html}
  {darkfina}
</div>"""
    return html


def _render_weekly_cards(results: list[dict], market: str, top_n: int = 10) -> str:
    """주간 분석 카드 (월요일용)."""
    filtered = [r for r in results if r["market"] == market.upper()][:top_n]
    if not filtered:
        return ""
    medals = ["🥇", "🥈", "🥉"]
    html = ""
    for i, r in enumerate(filtered):
        medal = medals[i] if i < 3 else f"{i+1}."
        price_fmt = f"${r['last_close']:,.2f}" if r["market"] == "US" else f"{r['last_close']:,.0f}"
        notes_html = "".join(f'<div class="note">• {n}</div>' for n in r["notes"][:3])
        darkfina = _darkfina_links(r["ticker"], r["market"]) if r["market"] == "US" else ""
        html += f"""
<div class="card">
  <div class="card-header">
    <span class="ticker"><span class="medal">{medal}</span> {r['name']} ({r['ticker']})</span>
    <span class="score-pos">+{r['score']}</span>
  </div>
  <div class="price">{price_fmt} | 주간 <span class="{_change_class(r['weekly_change'])}">{r['weekly_change']:+.1f}%</span> | 상승 {r['up_days']}일 / 하락 {r['down_days']}일</div>
  {notes_html}
  {darkfina}
</div>"""
    return html


def generate_kr_report(date_str: str, alerts: list[dict], out_dir: str = "reports", weekly_results: list[dict] | None = None) -> str:
    """한국 주식 HTML 리포트 생성."""
    Path(out_dir).mkdir(exist_ok=True)
    content = '<div class="section">기술적 분석</div>' + _render_analysis_cards(alerts)
    if weekly_results:
        weekly_html = _render_weekly_cards(weekly_results, "KR")
        if weekly_html:
            content += f'<div class="section">📅 주간 리뷰 + 금주 강세 예상</div>{weekly_html}'
    html = TEMPLATE.format(
        title=f"📊 {date_str} 한국 주식 분석",
        timestamp=f"생성: {date_str}",
        content=content,
    )
    path = Path(out_dir) / "kr.html"
    path.write_text(html, encoding="utf-8")
    return f"{PAGES_URL}/kr.html"


def generate_us_report(date_str: str, alerts: list[dict], surge_results: list[dict], out_dir: str = "reports", weekly_results: list[dict] | None = None) -> str:
    """미국 주식 HTML 리포트 생성."""
    Path(out_dir).mkdir(exist_ok=True)
    analysis_html = _render_analysis_cards(alerts)
    surge_html = _render_surge_cards(surge_results)
    content = f'<div class="section">기술적 분석</div>{analysis_html}<div class="section">🔍 급등 후보 TOP {len(surge_results)}</div>{surge_html}'
    if weekly_results:
        weekly_html = _render_weekly_cards(weekly_results, "US")
        if weekly_html:
            content += f'<div class="section">📅 주간 리뷰 + 금주 강세 예상</div>{weekly_html}'
    html = TEMPLATE.format(
        title=f"📊 {date_str} 미국 주식 분석",
        timestamp=f"생성: {date_str}",
        content=content,
    )
    path = Path(out_dir) / "us.html"
    path.write_text(html, encoding="utf-8")
    return f"{PAGES_URL}/us.html"


def generate_index(date_str: str, out_dir: str = "reports") -> None:
    """인덱스 페이지 생성."""
    Path(out_dir).mkdir(exist_ok=True)
    content = """
<div class="card">
  <a href="kr.html" style="color:#60a5fa;text-decoration:none;font-size:1.1rem;">🇰🇷 한국 주식 분석 →</a>
</div>
<div class="card">
  <a href="us.html" style="color:#60a5fa;text-decoration:none;font-size:1.1rem;">🇺🇸 미국 주식 분석 + 급등 후보 →</a>
</div>
"""
    html = TEMPLATE.format(
        title="📈 Stock Alert Bot",
        timestamp=f"최종 업데이트: {date_str}",
        content=content,
    )
    path = Path(out_dir) / "index.html"
    path.write_text(html, encoding="utf-8")
