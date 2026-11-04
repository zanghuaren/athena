# 所有表都要在这里导入，Alembic 才能发现
from app.models.base import Base

__all__ = ["Base"]
