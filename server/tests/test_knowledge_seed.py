from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Chapter, KnowledgePoint
from app.services.knowledge import KnowledgeCatalog, import_catalog

SEED_FILES = sorted((Path(__file__).parents[1] / "seed" / "knowledge").glob("*.json"))


def catalog(subject="math", chapters=None):
    return {
        "subject": subject,
        "chapters": chapters
        or [
            {
                "code": "M8-01",
                "grade": 8,
                "title": "三角形",
                "points": [{"code": "M8-01-01", "name": "三边关系", "description": "说明"}],
            }
        ],
    }


@pytest.mark.parametrize("path", SEED_FILES, ids=lambda p: p.name)
def test_seed_file_is_valid(path):
    data = KnowledgeCatalog.model_validate_json(path.read_text())
    points = [p for ch in data.chapters for p in ch.points]
    assert 80 <= len(points) <= 200
    assert len({p.code for p in points}) == len(points)


async def test_import_twice_updates_instead_of_duplicating():
    first = KnowledgeCatalog.model_validate(catalog())
    data = catalog()
    data["chapters"][0]["points"][0]["name"] = "三角形的三边关系"
    second = KnowledgeCatalog.model_validate(data)

    async with SessionLocal() as db:
        await import_catalog(db, first)
        await import_catalog(db, second)
        assert await db.scalar(select(func.count()).select_from(Chapter)) == 1
        point = (await db.scalars(select(KnowledgePoint))).one()
    assert point.name == "三角形的三边关系"
    assert point.grades == [8]


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (catalog(subject="physics"), "章节 M8-01 的编号应以 P8- 开头"),
        (
            catalog(
                chapters=[
                    {
                        "code": "M8-01",
                        "grade": 8,
                        "title": "三角形",
                        "points": [{"code": "M8-02-01", "name": "x", "description": "x"}],
                    }
                ]
            ),
            "应以章节编号 M8-01- 开头",
        ),
        (
            catalog(
                subject="english",
                chapters=[
                    {
                        "code": "E-01",
                        "grade": None,
                        "title": "名词",
                        "points": [{"code": "E-01-01", "name": "复数", "description": "x"}],
                    }
                ],
            ),
            "没有适用年级",
        ),
        (
            catalog(
                subject="physics",
                chapters=[
                    {
                        "code": "P8-01",
                        "grade": 8,
                        "title": "机械运动",
                        "points": [
                            {"code": "P8-01-01", "name": "x", "description": "x", "grades": [7]}
                        ],
                    }
                ],
            ),
            "年级不在本学科范围内",
        ),
    ],
)
def test_invalid_catalog_is_rejected(data, message):
    with pytest.raises(ValidationError, match=message):
        KnowledgeCatalog.model_validate(data)
