"""Check or restore the 30 photographs listed in manifest.jsonl."""

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="Restore missing photos and source labels")
    args = parser.parse_args()
    entries = [json.loads(line) for line in (ROOT / "manifest.jsonl").read_text().splitlines()]
    if len(entries) != 30 or len({e["sha256"] for e in entries}) != 30:
        raise SystemExit("Expected 30 unique photographs in the manifest")

    errors = []
    for entry in entries:
        path = ROOT / entry["file"]
        label = ROOT / entry["source_label"] if entry["source_label"] else None
        try:
            if args.fetch and (not path.exists() or (label and not label.exists())):
                restore(entry, path, label)
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ValueError("JPEG SHA-256 mismatch")
            if len(data) != entry["bytes"]:
                raise ValueError("JPEG size mismatch")
            if label:
                reference = json.loads(label.read_text())
                if reference["source_sample_id"] != entry["source_sample_id"]:
                    raise ValueError("Source label belongs to another sample")
            print(f"OK {entry['id']} {entry['width']}x{entry['height']}")
        except Exception as exc:
            errors.append(f"{entry['id']}: {exc}")

    for subject in ("math", "physics", "english"):
        count = sum(e["subject"] == subject for e in entries)
        if count != 10:
            errors.append(f"{subject}: expected 10 photographs, got {count}")
    if errors:
        raise SystemExit("\n".join(errors))
    print("Verified 30 unique JPEGs: math=10, physics=10, english=10; 20 source-label files.")
    print("This verifies materials only; no OCR accuracy has been measured.")


def download(url):
    request = Request(url, headers={"User-Agent": "tzb-ocr-materials/1.0"})
    with urlopen(request, timeout=90) as response:
        return response.read()


def restore(entry, path, label):
    if entry["source"] == "ExamOCRBench":
        query = urlencode({
            "dataset": "jiangxuhao/ExamOCRBench", "config": "task2", "split": "train",
            "offset": entry["source_row_index"], "length": 1,
        })
        row = json.loads(download("https://datasets-server.huggingface.co/rows?" + query))["rows"][0]["row"]
        if row["sample_id"] != entry["source_sample_id"]:
            raise ValueError("Upstream row changed; use the revision recorded in the manifest")
        original = base64.b64decode(row["image"]["bytes"])
        data = original
        reference = {
            "source_sample_id": row["sample_id"], "task": "task2",
            "ground_truth": json.loads(row["ground_truth_json"]),
        }
    else:
        from PIL import Image, ImageOps
        import pillow_heif

        original = download(entry["source_image_url"])
        pillow_heif.register_heif_opener()
        with Image.open(io.BytesIO(original)) as image:
            output = io.BytesIO()
            ImageOps.exif_transpose(image).convert("RGB").save(output, format="JPEG", quality=95)
            data = output.getvalue()

    if hashlib.sha256(original).hexdigest() != entry["source_sha256"]:
        raise ValueError("Upstream image changed; refusing to replace the recorded sample")
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError("JPEG encoding differs; install the pinned requirements in this directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if label:
        label.parent.mkdir(parents=True, exist_ok=True)
        label.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
