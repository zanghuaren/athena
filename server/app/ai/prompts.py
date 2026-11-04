from functools import cache
from pathlib import Path

_DIR = Path(__file__).resolve().parents[2] / "prompts"


@cache
def load(name: str) -> str:
    """读取 server/prompts/<name>.md。"""
    return (_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def render(name: str, **values: str) -> str:
    # 提示词里有 LaTeX 的花括号和美元符号，不能用 str.format / Template，只替换 {{key}}
    text = load(name)
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text
