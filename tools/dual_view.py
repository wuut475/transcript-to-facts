#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dual_view.py —— 双栏对照：成品里每一句，回到原文找命中行（零依赖，stdlib）

用法：
  python3 dual_view.py --minutes 成品稿.md --src 转录原文.txt --out 双栏对照.md

输出 markdown 表格：| 成品句 | 原文命中（L号 + 原句） | 相似度 | 判定 |
判定：✓ 高（≥0.75）/ ？ 中（0.45–0.75）/ ✗ 低（<0.45，回去查）

注意：这是筛子不是准确率。同义改写字面分会虚低，别把 ✗ 当"编造"。
"""
import argparse
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

KEEP = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")


def norm(text):
    text = unicodedata.normalize("NFKC", text).lower()
    return "".join(KEEP.findall(text))


def grams(text, n=3):
    return {text[i:i + n] for i in range(max(0, len(text) - n + 1))}


META = re.compile(r"^\s*-?\s*[\w\u4e00-\u9fff/\\. ]{1,16}[:：]")


def window_ratio(key, src, step=None):
    """在 src 里滑一个和 key 等长的窗，取最高相似度。
    摘录式摘要 vs 长句原文，整行比整句必然低分，所以必须按窗口比。"""
    if not src or not key:
        return 0.0
    if len(src) <= len(key) * 1.2:
        return SequenceMatcher(None, key, src).ratio()
    k = len(key)
    if step is None:
        step = max(1, k // 4)
    best = 0.0
    for start in range(0, len(src) - k + 1, step):
        r = SequenceMatcher(None, key, src[start:start + k]).ratio()
        if r > best:
            best = r
            if best > 0.95:
                break
    return best


def split_sentences(md):
    """按行 + 中文句号切，去 markdown 噪音，留下够长的句子"""
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    idx = md.find("\n## ")
    if idx > 0:                      # 丢掉第一个 "## " 之前的元信息区
        md = md[idx:]
    out = []
    for raw in md.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "|", "---", ">", "```")):
            continue
        if META.match(line):          # prov 元信息 / "来源文件：…" / "author: agent"
            continue
        line = re.sub(r"^\s*[-*]\s+", "", line)
        line = re.sub(r"〔L\d+[^〕]*〕", "", line)          # 去掉锚点本身
        line = re.sub(r"^〔[^〕]{1,6}〕", "", line.strip())    # 去掉 〔我方〕 这类标签
        line = re.sub(r"^(客户|我方|第三方)\s*[：:]\s*", "", line)  # 去掉说话人前缀
        line = re.sub(r"[*_`]", "", line)
        for piece in re.split(r"[。！？；\n]", line):
            piece = piece.strip()
            if len(norm(piece)) >= 8:
                out.append(piece)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--high", type=float, default=0.55)
    ap.add_argument("--low", type=float, default=0.30)
    ap.add_argument("--max-rows", type=int, default=0, help="0=全部")
    args = ap.parse_args()

    src_raw = Path(args.src).read_text(encoding="utf-8", errors="ignore").splitlines()
    src_norm = [norm(x) for x in src_raw]

    # 3-gram 倒排，先粗筛候选行
    index = {}
    for i, s in enumerate(src_norm):
        if not s:
            continue
        for g in grams(s):
            index.setdefault(g, set()).add(i)

    sents = split_sentences(Path(args.minutes).read_text(encoding="utf-8", errors="ignore"))
    if args.max_rows:
        sents = sents[: args.max_rows]

    rows, tally = [], {"✓": 0, "？": 0, "✗": 0}
    for sent in sents:
        key = norm(sent)
        if not key:
            continue
        key_grams = grams(key)
        hit = {}
        for g in key_grams:
            for i in index.get(g, ()):          # 统计每行命中的 gram 数
                hit[i] = hit.get(i, 0) + 1
        cand = set(hit)
        if not cand:
            cand = set(range(min(len(src_norm), 400)))
        best_i, best_r = None, 0.0
        # 候选太多时按 gram 命中数排序取前 60，控制耗时
        ranked = sorted(hit.items(), key=lambda kv: -kv[1])[:80] if hit else []
        for i in [x[0] for x in ranked]:
            r = window_ratio(key, src_norm[i])
            if r > best_r:
                best_i, best_r = i, r
        mark = "✓" if best_r >= args.high else ("？" if best_r >= args.low else "✗")
        tally[mark] += 1
        if best_i is None:
            rows.append((sent, "—", "—", 0.0, mark))
            continue
        snippet = src_raw[best_i].strip()
        if len(snippet) > 120:
            snippet = snippet[:120] + "…"
        rows.append((sent, f"L{best_i + 1}", snippet, best_r, mark))

    out = Path(args.out)
    lines = [
        "# 双栏对照（成品句 → 原文命中）",
        "",
        f"- 成品：`{args.minutes}`",
        f"- 原文：`{args.src}`",
        f"- 句数 {len(rows)}｜✓ {tally['✓']}｜？ {tally['？']}｜✗ {tally['✗']}",
        "- 说明：字面相似度只是筛子。✗ 不等于编造，可能是同义改写；✓ 也不证明意思对，仍要人看。",
        "",
        "| # | 成品句 | 原文命中 | 相似度 | 判定 |",
        "|---|---|---|---|---|",
    ]
    for n, (sent, ref, snippet, score, mark) in enumerate(rows, 1):
        s = sent.replace("|", "\\|")
        sn = snippet.replace("|", "\\|")
        lines.append(f"| {n} | {s} | {ref}：{sn} | {score:.2f} | {mark} |")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✓{tally['✓']}  ？{tally['？']}  ✗{tally['✗']}   共 {len(rows)} 句 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
