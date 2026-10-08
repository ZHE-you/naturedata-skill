#!/usr/bin/env bash
# 一键推送到 GitHub
# 用法: bash push.sh
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "仓库: $REPO_DIR"
echo "远程: $(git remote get-url origin)"
echo

# 检查是否已有 GitHub 仓库
echo "▶ 推送 main 分支到 origin ..."
echo "  （首次推送会弹出 Git Credential Manager 登录窗口，用 GitHub 账号授权即可）"
echo

git push -u origin main

echo
echo "✅ 完成！访问 https://github.com/ZHE-you/paper-batch-pipeline 查看"
