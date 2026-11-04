#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""term_audit.py —— 查「静默纠错」（零依赖）

冷测暴露：素材稿里"畅捷通"出现 11 次、原文只有 6 次，其余是 ASR 的"畅联通"被**默默改成**了正词，
没有留痕。人看不出改过什么，也就没法复核。

规则：素材稿每条的〔L号〕回到原文那一行；若原文那行有变体（畅联通/宁德/门价…）而素材稿写的是正词，
且该条**没有**标"原文"字样 → 报「静默纠错」，必须先留痕再往下走。

留痕写法：`畅捷通（原文"畅联通"）`

用法：
  python3 term_audit.py --src 转录原文.txt --md 素材稿.md [--terms 术语表.txt] [--allow]
退出码：0 无静默纠错 / 1 有（--allow 可忽略）
"""
import argparse
import re
import sys
from pathlib import Path

DEFAULT_TERMS = [
    ("金蝶", ["经典", "金姐", "进碟"]),
    ("畅捷通", ["畅联通", "畅云"]),
    ("园姐", ["袁姐"]),
    ("门架", ["门价", "仪架"]),
    ("林德", ["宁德"]),
    ("报损仓", ["报成仓", "报存仓"]),
    ("二手叉车", ["二手茶"]),
    ("领料", ["领药"]),
]

ANCHOR = re.compile(r"〔L(\d+)(?:#(\d+))?(?:\s*[-–~]\s*L?(\d+))?[^〕]*〕")


def load_terms(path):
    terms = list(DEFAULT_TERMS)
    if path:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            good, bad = line.split("=", 1)
            terms.append((good.strip(), [b.strip() for b in re.split(r"[,，]", bad) if b.strip()]))
    return terms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--md", required=True)
    ap.add_argument("--terms")
    ap.add_argument("--allow", action="store_true", help="有静默纠错也返回 0")
    ap.add_argument("--max-show", type=int, default=12)
    args = ap.parse_args()

    src = Path(args.src).read_text(encoding="utf-8", errors="ignore").splitlines()
    md = Path(args.md).read_text(encoding="utf-8", errors="ignore")
    idx = md.find("\n## ")
    body = md[idx:] if idx > 0 else md
    terms = load_terms(args.terms)

    silent, traced, unresolved = [], [], []
    for line in body.splitlines():
        if not re.match(r"^\s{0,4}[-*]\s+", line):
            continue
        m = ANCHOR.search(line)
        if not m:
            continue
        ln = int(m.group(3) or m.group(1))
        if not (1 <= ln <= len(src)):
            continue
        src_line = src[ln - 1]
        has_trace = "原文" in line
        for good, bads in terms:
            if good not in line:
                continue
            hit = [b for b in bads if b in src_line and good not in src_line]
            if not hit:
                continue
            if has_trace:
                traced.append(ln)
            else:
                silent.append((ln, good, hit[0], line.strip()[:70]))

    # 反向：素材稿里的正词全文计数 vs 原文计数（判断有没有系统性静默替换）
    print("══ term_audit")
    for good, bads in terms:
        n_md, n_src = body.count(good), "\n".join(src).count(good)
        if n_md and n_md > n_src:
            print(f"   {good}：素材稿 {n_md} 次 / 原文 {n_src} 次"
                  + ("  ← 超出的可能是静默纠错" if n_md - n_src >= 2 else ""))
        for b in bads:
            if b not in body:
                continue
            pos = body.find(b)
            ctx = body[max(0, pos - 30): pos + len(b) + 30]
            if "原文" in ctx or "订正" in ctx:
                continue                      # 是留痕/订正清单里的引用，不算
            unresolved.append((b, good))

    print(f"   已留痕 {len(traced)} 处｜静默纠错 {len(silent)} 处｜未标注的变体 {len(unresolved)} 种")
    if silent:
        print("   ✗ 静默纠错（原文是错字、你写成了正词、但没留痕）：")
        for ln, good, bad, ctx in silent[: args.max_show]:
            print(f"     L{ln}  {bad}→{good}   {ctx}")
        if len(silent) > args.max_show:
            print(f"     …另有 {len(silent) - args.max_show} 处")
        print("   改法：写成 {}（原文「{}」）".format(silent[0][1], silent[0][2]))
    if unresolved:
        print("   ？正文里还留着变体：" + "、".join(f"{b}→{g}" for b, g in unresolved[:8]))

    if silent and not args.allow:
        print("\n结论: FAIL —— 先留痕（改完重跑）")
        return 1
    print("\n结论: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
