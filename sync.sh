#!/usr/bin/env bash
# 把本机技能目录的改动同步到本仓库，然后你自己 commit + push。
#
# 为什么不是无脑 cp 全部：
#   本机的 SKILL.md 和 tools/check_material.py 跟仓库版**故意不一样**。
#   本机版含真实客户名、客户专用术语（喂 ASR 用得上）；
#   仓库版是脱敏版，术语表只留通用词。
#   所以这两个文件只提示差异，不自动覆盖，避免把客户实名推到公开仓库。
#
# 用法：
#   ./sync.sh          # 同步可直接同步的文件，其余只显示差异
#   ./sync.sh --apply  # 连 SKILL.md 也覆盖（自己确认已脱敏再用）

set -euo pipefail

LOCAL="${HOME}/.dsh/skills/transcript-to-facts"
REPO="$(cd "$(dirname "$0")" && pwd)"
APPLY="${1:-}"

if [ ! -d "$LOCAL" ]; then
  echo "✗ 找不到本机技能目录：$LOCAL"
  exit 1
fi

echo "本机： $LOCAL"
echo "仓库： $REPO"
echo

# ---- 可以安全直接同步的 ----
safe_sync() {
  local rel="$1"
  if [ -f "$LOCAL/$rel" ]; then
    cp "$LOCAL/$rel" "$REPO/$rel"
    echo "  ✓ 同步 $rel"
  fi
}
echo "同步无差异文件："
safe_sync "references/prompts.md"
safe_sync "tools/dual_view.py"

# ---- 故意不同的，只提示 ----
echo
if [ "$APPLY" = "--apply" ]; then
  echo "⚠ --apply：覆盖 SKILL.md（请先确认客户信息已脱敏）"
  cp "$LOCAL/SKILL.md" "$REPO/SKILL.md"
else
  echo "SKILL.md（脱敏版，不自动覆盖；用 diff 看本机改了什么）"
  diff -u "$REPO/SKILL.md" "$LOCAL/SKILL.md" | head -60 || true
fi

echo
echo "tools/check_material.py（仓库版术语表已清空客户专用词，不自动覆盖）"
diff -u "$REPO/tools/check_material.py" "$LOCAL/tools/check_material.py" | head -60 || true

echo
echo "── git 状态 ──"
git -C "$REPO" status --short || true
echo
echo "确认无误后："
echo "  cd \"$REPO\" && git add -A && git commit -m \"sync from local skill\" && git push"
