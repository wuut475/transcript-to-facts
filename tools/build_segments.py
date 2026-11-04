#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_segments.py —— 把转录原文切成「可定位的子段」（零依赖）

解决冷测暴露的两条：① 行长太粗（L122 一行 6078 字符、含 8 个话题）② 说话人标签整段吞掉换人。

产出 `段落索引.tsv`：seg_id / src_line / k / chars / speaker / flags / text
seg_id 形如 L122#3 —— 第 122 行的第 3 个子段。抽取时拿它当锚点，比行号精确一级。

用法：
  python3 build_segments.py --src 转录原文.txt --out 段落索引.tsv
  python3 build_segments.py --src … --out … --max-chars 300
"""
import argparse
import re
import sys
from pathlib import Path

SPK = re.compile(r"^(发言人\d+)[：:]")
SENT = re.compile(r"[^。！？；!?;\n]+[。！？；!?;]?")
# 接电话/中断的开口语：这些地方极可能是外部来电插进来，换人但没换标签
CALL = re.compile(r"(^|[。！？，,\s])(喂[，,。！!\s]|哎[，,]\s*你好|你好[，,]\s*(哪位|我是)|抱歉[，,]\s*我(接|来)|不好意思[，,]\s*接个电话|稍等[，,]\s*接个电话)")
LONG_LINE = 800          # 单行超这个长度就标「长行」
LONG_SEG = 300           # 单段目标长度


def split_line(body, max_chars):
    """按句切，累加到 max_chars 左右为一段；单句超长再按逗号兜底"""
    pieces = []
    buf = ""
    for sent in SENT.findall(body):
        sent = sent.strip()
        if not sent:
            continue
        if len(buf) + len(sent) > max_chars and buf:
            pieces.append(buf)
            buf = sent
        else:
            buf += sent
    if buf:
        pieces.append(buf)

    out = []
    for p in pieces:
        if len(p) <= max_chars * 1.8:
            out.append(p)
            continue
        # 超长单句：按逗号硬切
        buf = ""
        for part in re.split(r"(?<=[，,])", p):
            if len(buf) + len(part) > max_chars and buf:
                out.append(buf)
                buf = part
            else:
                buf += part
        if buf:
            out.append(buf)
    return out


def flags_for(text, line_len, speaker=None):
    f = []
    if speaker and speaker not in ("发言人1", "发言人2", "?"):
        f.append("第三方")          # 现场只有两方；第三个标签基本是外部来电/插话
    if line_len > LONG_LINE:
        f.append("长行")
    if CALL.search(text):
        f.append("疑似来电")
    if text.count("？") + text.count("?") >= 3:
        f.append("多问句")
    if len(text) > LONG_SEG * 1.8:
        f.append("单段超长")
    return ",".join(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-chars", type=int, default=LONG_SEG)
    args = ap.parse_args()

    lines = Path(args.src).read_text(encoding="utf-8", errors="ignore").splitlines()
    rows = []
    stat = {"行": 0, "段": 0, "长行": 0, "来电": 0, "多问句": 0, "第三方": 0}

    for i, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        stat["行"] += 1
        if len(raw) > LONG_LINE:
            stat["长行"] += 1
        m = SPK.match(raw)
        speaker = m.group(1) if m else "?"
        body = raw[m.end():] if m else raw
        segs = split_line(body, args.max_chars) or [""]
        for k, seg in enumerate(segs, 1):
            f = flags_for(seg, len(raw), speaker)
            if "疑似来电" in f:
                stat["来电"] += 1
            if "第三方" in f:
                stat["第三方"] += 1
            if "多问句" in f:
                stat["多问句"] += 1
            stat["段"] += 1
            seg = seg.replace("\t", " ").replace("\n", " ")
            rows.append(f"L{i}#{k}\t{i}\t{k}\t{len(seg)}\t{speaker}\t{f}\t{seg}")

    Path(args.out).write_text(
        "seg_id\tsrc_line\tk\tchars\tspeaker\tflags\ttext\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    print("══ build_segments")
    print(f"   行 {stat['行']}｜子段 {stat['段']}｜长行(>{LONG_LINE}) {stat['长行']}｜疑似来电 {stat['来电']}｜第三方标签 {stat['第三方']}｜多问句 {stat['多问句']}")
    print(f"   → {args.out}")
    if stat["长行"]:
        print(f"   ⚠ {stat['长行']} 行超长，行号只能定位到行；抽取时请用 seg_id（L122#3）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
