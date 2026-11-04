"""给一次 run.py 的输出计分：印刷体、手写分开，按字符算准确率。

    python3 eval/homework-ocr/score.py eval/homework-ocr/runs/<时间>

准确率 = 1 - 错误字符数 / 参考字符数，按 Flexible Character Accuracy 的思路计算：
先反复找两边最长的相同片段（≥ 3 个字）配对，剩下的部分再算编辑距离，
所以题目顺序、题目怎么分段不影响结果，只有认错、漏掉、多出来的字算错。
比对前统一全角半角、去掉空白和填空线（见 normalize）。
"""

import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MIN_MATCH = 3
TARGET = {"printed": 0.95, "handwritten": 0.85}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"-{3,}|[_|$^]", "", text)
    # 选择题的空括号、填空括号两边写法不一，不算内容
    return re.sub(r"\(\)", "", text)


def errors(refs: list[str], hyps: list[str]) -> tuple[int, int]:
    """返回（错误字符数，参考字符数）。"""
    ref = "\x00".join(normalize(s) for s in refs)
    hyp = "\x03".join(normalize(s) for s in hyps)
    total = len(ref.replace("\x00", ""))
    while True:
        m = SequenceMatcher(None, ref, hyp, autojunk=False).find_longest_match()
        if m.size < MIN_MATCH:
            break
        # 配对过的片段换成两边不会再相同的占位符，相当于从两边拿掉
        ref = ref[: m.a] + "\x00" * m.size + ref[m.a + m.size :]
        hyp = hyp[: m.b] + "\x03" * m.size + hyp[m.b + m.size :]
    return levenshtein(ref.replace("\x00", ""), hyp.replace("\x03", "")), total


def levenshtein(a: str, b: str) -> int:
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, cb in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (ca != cb))
    return row[-1]


def score_page(reference: dict, result: dict) -> dict[str, tuple[int, int] | None]:
    questions = reference["questions"]
    hyp = result.get("output", {"questions": []})["questions"]
    scores: dict[str, tuple[int, int] | None] = {}
    printed = [q["printed"] for q in questions if q["printed"]]
    # 印刷体看不清的页、纯手写的页不评印刷体；有整题不评测的页，多认出来的字没法判断对错，不评手写
    if reference.get("printed_excluded") or not printed:
        scores["printed"] = None
    else:
        scores["printed"] = errors(printed, [q["printed"] for q in hyp])
    if any(q.get("exclude") for q in questions):
        scores["handwritten"] = None
    else:
        refs = [h for q in questions for h in q["handwritten"]]
        scores["handwritten"] = errors(refs, [h for q in hyp for h in q["handwritten"]])
    return scores


def accuracy(pairs: list[tuple[int, int]]) -> str:
    err, total = sum(p[0] for p in pairs), sum(p[1] for p in pairs)
    return f"{max(0.0, 1 - err / total):.1%}（{total} 字）" if total else "—"


def main() -> None:
    run = Path(sys.argv[1])
    entries = [json.loads(line) for line in (ROOT / "manifest.jsonl").read_text().splitlines()]
    rows, groups = [], {}
    for e in entries:
        reference = json.loads((ROOT / "references" / f"{e['id']}.json").read_text())
        result = json.loads((run / f"{e['id']}.json").read_text())
        scores = score_page(reference, result)
        for kind, pair in scores.items():
            if pair is None:
                continue
            for group in ("全部", e["subject"], e["quality"]):
                groups.setdefault((kind, group), []).append(pair)
        cells = [accuracy([p]) if p else "不评" for p in scores.values()]
        ms = result.get("ms", "失败")
        rows.append(f"| {e['id']} | {e['quality']} | {' | '.join(cells)} | {ms} |")

    lines = ["| 分组 | 印刷体 | 手写 |", "| --- | --- | --- |"]
    for group in ("全部", "math", "physics", "english", "regular", "challenging"):
        cells = [accuracy(groups.get((kind, group), [])) for kind in TARGET]
        lines.append(f"| {group} | {' | '.join(cells)} |")
    lines += ["", f"门槛：印刷体 ≥ {TARGET['printed']:.0%}，手写 ≥ {TARGET['handwritten']:.0%}", ""]
    lines += ["| 照片 | 质量 | 印刷体 | 手写 | 耗时 ms |", "| --- | --- | --- | --- | --- |", *rows]
    report = "\n".join(lines) + "\n"
    (run / "report.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
