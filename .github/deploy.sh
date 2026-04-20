#!/bin/bash
# gh-pages 배포 공통 스크립트
# Usage: bash .github/deploy.sh "commit message"

set -e

COMMIT_MSG="${1:-Update reports}"
REPO_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/seyoungkwon29/stock-alert-bot.git"

# 기존 gh-pages 클론 (이미 있으면 재사용)
if [ ! -d "gh-pages-dir/.git" ]; then
  rm -rf gh-pages-dir
  git clone --branch gh-pages --single-branch "$REPO_URL" gh-pages-dir 2>/dev/null || mkdir -p gh-pages-dir
fi

# 리포트 파일 복사
cp reports/*.html gh-pages-dir/ 2>/dev/null || true
cp reports/*.json gh-pages-dir/ 2>/dev/null || true

# PWA 파일 복사
cp public/manifest.json gh-pages-dir/ 2>/dev/null || true
cp public/sw.js gh-pages-dir/ 2>/dev/null || true
cp public/icon-*.png gh-pages-dir/ 2>/dev/null || true

cd gh-pages-dir
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
git add -A
git commit -m "$COMMIT_MSG" || echo "No changes"
git push -f "$REPO_URL" gh-pages

# Vercel 재배포 (Vercel deploy hook이 설정된 경우)
if [ -n "$VERCEL_DEPLOY_HOOK" ]; then
  curl -s -X POST "$VERCEL_DEPLOY_HOOK" || echo "Vercel deploy hook failed"
fi
