"""C5 回归：30 张照片走一遍整页批改（开发环境的 api + worker），按题统计，写出 report.md。

    python3 eval/homework-ocr/grade.py              # 批改并出报告，结果在 runs/grade-<时间>/
    python3 eval/homework-ocr/grade.py --concurrency 3   # 同时提交 3 页，看多人同时批改的耗时
    python3 eval/homework-ocr/grade.py --report runs/grade-<时间>   # 只按已有结果重新出报告

只用标准库，在宿主机上运行；api 要在 127.0.0.1:8000，worker 要在跑。每次注册一个新学生提交。
没有判分的标准答案，对错只统计分布，判得对不对要看 details.md 人工核对。

手写准确率和 score.py 同一种算法：整页的识别作答对整页的参考手写，“？”题没读出作答的算漏字。
红笔、划改：参考转写的备注里写了“X”是老师订正 / 被划掉 / 不计的，作答里出现 X 就算混进来了。
"""

import argparse
import json
import re
import statistics
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError

from score import errors, normalize

ROOT = Path(__file__).resolve().parent
API = "http://127.0.0.1:8000/api/v1"
POLL_SECONDS = 2
# 识别出的作答按产品要求用 LaTeX 写公式，参考转写是纯文字；比对前换成参考转写的写法
LATEX_SYMBOLS = {
    r"\div": "÷",
    r"\times": "×",
    r"\cdot": "·",
    r"\circ": "°",
    r"\bigcirc": "○",
    r"\Delta": "Δ",
    r"\triangle": "△",
    r"\angle": "∠",
    r"\pi": "π",
    r"\ge": "≥",
    r"\geq": "≥",
    r"\le": "≤",
    r"\leq": "≤",
    r"\neq": "≠",
    r"\ne": "≠",
    r"\approx": "≈",
    r"\cdots": "…",
    r"\sim": "~",
    r"\quad": " ",
    r"\left": "",
    r"\right": "",
}
FRACTION = re.compile(r"\\d?frac\{([^{}]*)\}\{([^{}]*)\}")
COMMAND_ARG = re.compile(r"\\(?:text|mathrm|underline|boxed)\{([^{}]*)\}")
SQRT = re.compile(r"\\sqrt\{([^{}]*)\}")
EXCLUDED = re.compile(r"“([^”]{2,})”(?:和[^，。；]*)?(?:被划掉|是老师订正|不计)")


def call(method: str, path: str, token: str | None = None, body=None, files=None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    data = None
    if files is not None:
        boundary = uuid.uuid4().hex
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        data = (
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="file"; filename="photo.jpg"\r\n'
                "Content-Type: image/jpeg\r\n\r\n"
            ).encode()
            + files
            + f"\r\n--{boundary}--\r\n".encode()
        )
    elif body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    request = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        raise RuntimeError(f"{method} {path} {exc.code}: {exc.read().decode()}") from exc


def register() -> str:
    username = "eval" + datetime.now().strftime("%m%d%H%M%S")
    password = "abc12345"
    body = {
        "role": "student",
        "username": username,
        "password": password,
        "display_name": "回归",
        "grade": 8,
    }
    call("POST", "/auth/register", body=body)
    return call("POST", "/auth/login", body={"username": username, "password": password})["token"]


def grade_one(token: str, entry: dict, out_dir: Path) -> None:
    photo = (ROOT / entry["file"]).read_bytes()
    file = call("POST", "/files", token, files=photo)
    started = time.monotonic()
    created = call("POST", "/scans", token, body={"image_file_id": file["id"]})
    while (job := call("GET", f"/jobs/{created['job_id']}", token))["status"] not in (
        "succeeded",
        "failed",
    ):
        time.sleep(POLL_SECONDS)
    seconds = round(time.monotonic() - started)
    scan = call("GET", f"/scans/{created['scan']['id']}", token)
    result = {"id": entry["id"], "seconds": seconds, "error": job["error"], "scan": scan}
    (out_dir / f"{entry['id']}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(entry["id"], seconds, job["status"], flush=True)


def plain(text: str) -> str:
    while True:
        replaced = SQRT.sub(r"√\1", COMMAND_ARG.sub(r"\1", FRACTION.sub(r"\1/\2", text)))
        if replaced == text:
            break
        text = replaced
    text = re.sub(r"\\[a-zA-Z]+", lambda m: LATEX_SYMBOLS.get(m.group(), m.group()), text)
    return text.replace("{", "").replace("}", "")


def answer_texts(answer: dict | None) -> list[str]:
    """识别出的作答拆成一段段文字，和参考转写的 handwritten 对得上。"""
    if answer is None:
        return []
    if "text" in answer:
        return [answer["text"]]
    if "sub" in answer:
        return [t for part in answer["sub"] for t in answer_texts(part)]
    if answer.get("choice"):
        return ["".join(answer["choice"])]
    if answer.get("judge") is not None:
        return ["√" if answer["judge"] else "×"]
    return [b for b in answer.get("blanks") or [] if b]


def mark(item: dict) -> str:
    attempt = item["attempt"]
    if attempt is None:
        return "?"
    if attempt["grading_status"] == "pending":
        return "pending"
    return attempt["result"]


def page_stats(reference: dict, result: dict) -> dict:
    scan = result["scan"]
    items = scan["items"]
    marks = [mark(i) for i in items]
    hyps = [plain(t) for i in items for t in answer_texts(i["answer"])]
    questions = reference["questions"]
    handwritten = None
    if scan["status"] == "done" and not any(q.get("exclude") for q in questions):
        refs = [h for q in questions for h in q["handwritten"]]
        if refs:
            handwritten = errors(refs, hyps)
    joined = normalize("".join(hyps))
    leaked = [
        text
        for q in questions
        for text in EXCLUDED.findall(q.get("note", ""))
        if normalize(text) in joined
    ]
    checked = [text for q in questions for text in EXCLUDED.findall(q.get("note", ""))]
    return {
        "status": scan["fail_reason"] or scan["status"],
        "questions": len(items),
        "marks": {m: marks.count(m) for m in ("correct", "partial", "wrong", "?", "pending")},
        "types": [i["question"]["type"] for i in items],
        "handwritten": handwritten,
        "leaked": leaked,
        "checked": checked,
        "seconds": result["seconds"],
        "truncated": scan["truncated"],
    }


def accuracy(pairs: list[tuple[int, int]]) -> str:
    err, total = sum(p[0] for p in pairs), sum(p[1] for p in pairs)
    return f"{max(0.0, 1 - err / total):.1%}（{total} 字）" if total else "—"


def report(run: Path) -> None:
    entries = [json.loads(line) for line in (ROOT / "manifest.jsonl").read_text().splitlines()]
    rows, details, stats = [], [], []
    for e in entries:
        path = run / f"{e['id']}.json"
        if not path.exists():  # 中途停掉的一次，只统计跑完的页
            continue
        reference = json.loads((ROOT / "references" / f"{e['id']}.json").read_text())
        result = json.loads(path.read_text())
        s = page_stats(reference, result) | {"entry": e}
        stats.append(s)
        m = s["marks"]
        rows.append(
            f"| {e['id']} | {e['quality']} | {s['status']} | {s['questions']} "
            f"| {m['correct']} / {m['partial']} / {m['wrong']} / {m['?']} / {m['pending']} "
            f"| {accuracy([s['handwritten']]) if s['handwritten'] else '不评'} "
            f"| {'、'.join(s['leaked']) or ''} | {s['seconds']} |"
        )
        details.append(page_details(e["id"], result))

    done = [s for s in stats if s["status"] == "done"]
    total = sum(s["questions"] for s in done)
    marks = {k: sum(s["marks"][k] for s in done) for k in done[0]["marks"]}
    failed = {k: sum(s["status"] == k for s in stats) for k in ("unclear", "no_question", "error")}
    by_group = {
        g: accuracy(
            [
                s["handwritten"]
                for s in done
                if s["handwritten"] and g in ("全部", s["entry"]["subject"], s["entry"]["quality"])
            ]
        )
        for g in ("全部", "math", "physics", "english", "regular", "challenging")
    }
    seconds = [s["seconds"] for s in done]
    small = [s["seconds"] for s in done if s["questions"] <= 10]
    concurrency = json.loads((run / "meta.json").read_text())["concurrency"]
    lines = [
        f"同时提交 {concurrency} 页",
        "",
        f"- 页数：{len(stats)}，批完 {len(done)}，"
        + "，".join(f"{k} {v}" for k, v in failed.items()),
        # 参考转写按作答区分题（一道计算大题的每个小算式算一题），题数和批改的题数不能直接比
        f"- 题数：{total}",
        "- 结果：" + "，".join(f"{k} {v}（{v / total:.0%}）" for k, v in marks.items()),
        "- 手写准确率：" + "，".join(f"{g} {a}" for g, a in by_group.items()),
        f"- 红笔、划掉的字混进作答：{sum(len(s['leaked']) for s in stats)} / "
        f"{sum(len(s['checked']) for s in stats)} 处",
        f"- 每页耗时：中位数 {statistics.median(seconds)} 秒，最长 {max(seconds)} 秒；"
        f"10 题以内的页中位数 {statistics.median(small) if small else '—'} 秒",
        "",
        "| 照片 | 质量 | 状态 | 题数 | 对 / 部分 / 错 / ？ / 待判 | 手写 | 混进作答 | 秒 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        *rows,
    ]
    text = "\n".join(lines) + "\n"
    (run / "report.md").write_text(text, encoding="utf-8")
    (run / "details.md").write_text("\n".join(details), encoding="utf-8")
    print(text)


def page_details(page_id: str, result: dict) -> str:
    """逐题列出题型、题干开头、识别的作答、答案和结果，人工核对判分用。"""
    scan = result["scan"]
    lines = [f"## {page_id}（{scan['fail_reason'] or scan['status']}，{result['seconds']} 秒）", ""]
    if result["error"]:
        lines += [f"失败：{result['error']['message']}", ""]
    for item in scan["items"]:
        q = item["question"]
        stem = q["content"]["stem"].replace("\n", " ")[:60]
        answer = " / ".join(answer_texts(item["answer"])) or "（没读到）"
        key = json.dumps(q["answer"], ensure_ascii=False)[:80]
        attempt = item["attempt"] or {}
        summary = ((attempt.get("grading_detail") or {}).get("summary") or "")[:60]
        lines.append(
            f"- {item['seq']}. [{q['type']}] {stem}\n  作答：{answer}；答案：{key}；"
            f"结果：{mark(item)} {attempt.get('score')}/{attempt.get('max_score')} {summary}"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, help="只按这次已有的结果重新出报告")
    parser.add_argument("--concurrency", type=int, default=1, help="同时提交几页")
    args = parser.parse_args()
    if args.report:
        report(args.report)
        return
    out_dir = ROOT / "runs" / ("grade-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    out_dir.mkdir(parents=True)
    (out_dir / "meta.json").write_text(json.dumps({"concurrency": args.concurrency}) + "\n")
    token = register()
    entries = [json.loads(line) for line in (ROOT / "manifest.jsonl").read_text().splitlines()]
    with ThreadPoolExecutor(args.concurrency) as pool:
        list(pool.map(lambda e: grade_one(token, e, out_dir), entries))
    report(out_dir)


if __name__ == "__main__":
    main()
