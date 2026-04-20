#!/bin/bash
# gh-pages + Vercel 배포 공통 스크립트
# Usage: bash .github/deploy.sh "commit message"

set -e

COMMIT_MSG="${1:-Update reports}"
REPO_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/seyoungkwon29/stock-alert-bot.git"

# 배포용 디렉토리 준비 (기존 gh-pages 파일 보존)
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
cp public/index.html gh-pages-dir/ 2>/dev/null || true

# GitHub Pages 배포
cd gh-pages-dir
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
git add -A
git commit -m "$COMMIT_MSG" || echo "No changes"
git push -f "$REPO_URL" gh-pages
cd ..

# Vercel 배포
if [ -n "$VERCEL_TOKEN" ]; then
  echo "🚀 Vercel 배포 중..."
  npx vercel deploy gh-pages-dir --prod --yes \
    --token="$VERCEL_TOKEN" \
    --scope="$VERCEL_ORG_ID" \
    2>&1 || echo "⚠️ Vercel 배포 실패 (GitHub Pages는 정상)"
fi
