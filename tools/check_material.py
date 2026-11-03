#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_material.py —— 素材稿门禁（零依赖，stdlib）

查五件事：
  1. 覆盖声明在不在（"覆盖范围：L1–L482 …"）
  2. 每条 bullet 有没有〔L行号〕
  3. 行号有没有越界（大于原文行数）
  4. 字数比是否落在 1/5–1/3（默认 0.18–0.36）
  5. 术语变体 / 存疑标记统计

用法：
  python3 check_material.py --src 转录原文.txt --md 素材稿.md
  python3 check_material.py --src … --md … --terms 术语表.txt   # 每行 "正确词=错1,错2"
退出码：0 全过；1 有 FAIL
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

# 中文常见同音误识（可被 --terms 覆盖/追加）
DEFAULT_TERMS = [
    # 只保留跨客户通用的产品名/竞品名；行业专用词（门架、报损仓、领料、二手叉车等）
    # 属于具体客户，不要写进默认值——用 --terms 词表.txt 传，每行「正确词=错1,错2」
    ("金蝶", ["经典", "金姐", "进碟", "金叠"]),
    ("畅捷通", ["畅联通", "畅云", "畅通捷"]),
]

CJK = re.compile(r"[\u4e00-\u9fff]")


def norm_len(text):
    """算汉字数（全角/半角统一后统计 CJK 字符）"""
    text = unicodedata.normalize("NFKC", text)
    return len(CJK.findall(text))


def load_terms(path):
    terms = list(DEFAULT_TERMS)
    if path:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            good, bad = line.split("=", 1)
            bad_list = [b.strip() for b in re.split(r"[,，]", bad) if b.strip()]
            terms.append((good.strip(), bad_list))
    return terms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="转录原文（行号基准）")
    ap.add_argument("--md", required=True, help="素材稿")
    ap.add_argument("--terms", help="自定义术语表：每行 正确词=错1,错2")
    ap.add_argument("--min-ratio", type=float, default=0.18)
    ap.add_argument("--max-ratio", type=float, default=0.36)
    args = ap.parse_args()

    src = Path(args.src).read_text(encoding="utf-8", errors="ignore")
    md_raw = Path(args.md).read_text(encoding="utf-8", errors="ignore")
    # 正文 = 去掉 prov 注释块、丢掉第一个 "## " 之前的元信息区
    md_nc = re.sub(r"<!--.*?-->", "", md_raw, flags=re.S)
    idx = md_nc.find("\n## ")
    md = md_nc[idx:] if idx > 0 else md_nc
    src_lines = src.count("\n") + 1
    src_chars = norm_len(src)
    md_chars = norm_len(md)
    ratio = md_chars / src_chars if src_chars else 0.0

    fails, warns, oks = [], [], []
    print("══ check_material")
    print(f"   原文 {src_lines} 行 / {src_chars} 汉字")
    print(f"   素材 {md_chars} 汉字 → 压缩比 {ratio:.3f}")

    # 1 覆盖声明
    if re.search(r"覆盖\s*(范围|原文|全文)", md_raw) and re.search(r"L\d+", md_raw):
        oks.append("[1] 覆盖声明 ✓")
    elif re.search(r"L\d+\s*[-–~至]\s*L\d+", md_raw):
        warns.append("[1] 覆盖声明 ？ 只看到行号区间，没写清覆盖/丢弃范围")
    else:
        fails.append("[1] 覆盖声明 ✗ 头部缺『覆盖范围：Lx–Ly，丢弃…』")

    # 2/3 bullet 与行号
    bullets = [
        ln for ln in md.splitlines()
        if re.match(r"^\s{0,4}[-*]\s+", ln) and not ln.startswith("<!--")
    ]
    LREF = re.compile(r"〔L(\d+)(?:\s*[-–~]\s*L?(\d+))?")
    no_ref, out_of_range = [], []
    for b in bullets:
        m = LREF.search(b)
        if not m:
            no_ref.append(b.strip()[:60])
            continue
        end = int(m.group(2) or m.group(1))
        if end > src_lines:
            out_of_range.append((end, b.strip()[:50]))

    if bullets and not no_ref:
        oks.append(f"[2] 行号锚点 ✓ {len(bullets)} 条全有〔L号〕")
    elif no_ref:
        fails.append(f"[2] 行号锚点 ✗ {len(no_ref)}/{len(bullets)} 条没行号（示例：{no_ref[0]}）")
    else:
        warns.append("[2] 行号锚点 ？ 没找到任何 bullet")

    if out_of_range:
        fails.append(f"[3] 行号越界 ✗ {len(out_of_range)} 条（最大 L{max(x[0] for x in out_of_range)} > 原文 {src_lines} 行）")
    else:
        oks.append("[3] 行号未越界 ✓")

    # 4 字数比
    if args.min_ratio <= ratio <= args.max_ratio:
        oks.append(f"[4] 压缩比 ✓ {ratio:.2f} 在 {args.min_ratio:.2f}–{args.max_ratio:.2f}")
    elif ratio > args.max_ratio:
        fails.append(f"[4] 压缩比 ✗ {ratio:.2f} 太高，你在抄不是在抽（上限 {args.max_ratio:.2f}）")
    else:
        warns.append(f"[4] 压缩比 ？ {ratio:.2f} 偏低，当心把客户真说过的话筛掉了（下限 {args.min_ratio:.2f}）")

    # 5 术语变体
    hits = []
    for good, bads in load_terms(args.terms):
        for bad in bads:
            if not bad:
                continue
            for ln in md.splitlines():
                if "原文" in ln or "订正" in ln:
                    continue
                if bad in ln:
                    hits.append(f"{bad}→{good}×1")
                    break
    if hits:
        fails.append("[5] 术语变体 ✗ " + "、".join(hits[:8]))
    else:
        oks.append("[5] 术语变体 ✓ 无")

    # 统计
    stats = {
        "客户": len(re.findall(r"客户：", md)),
        "我方": len(re.findall(r"我方：", md)),
        "第三方": len(re.findall(r"第三方", md)),
        "归属存疑": md.count("〔归属存疑〕"),
        "听不清": md.count("〔听不清〕"),
    }
    print("   分项：" + "  ".join(f"{k}{v}" for k, v in stats.items()))

    for line in oks:
        print("  " + line)
    for line in warns:
        print("  " + line)
    for line in fails:
        print("  " + line)

    if fails:
        print(f"\n结论: FAIL（{len(fails)} 项）—— 修完再进下游")
        return 1
    print("\n结论: PASS" + ("（有警告，看一眼）" if warns else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
