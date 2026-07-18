"""分页与通用工具。

分页规范（性能落地要求）：
- 所有列表查询统一走 `Pagination`，避免全表扫描 + 无界返回。
- page 从 1 起；page_size 受 max_page_size 限制，防止恶意大分页。
- 返回统一信封 `paginate_result`，包含 items / page / pageSize / total / hasMore。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from .config import settings


def make_id(prefix: str) -> str:
    """生成带前缀的短 id。"""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@dataclass(frozen=True)
class Pagination:
    """规范化的分页参数。"""

    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def normalize_pagination(page: Optional[int], page_size: Optional[int]) -> Pagination:
    """把外部传入的分页参数收敛到安全范围内。"""
    safe_page = page if page and page > 0 else 1
    default_size = settings.default_page_size
    max_size = settings.max_page_size
    size = page_size if page_size and page_size > 0 else default_size
    size = min(size, max_size)
    return Pagination(page=safe_page, page_size=size)


def paginate_result(items: list, total: int, pagination: Pagination) -> dict:
    """统一分页返回信封。"""
    return {
        "items": items,
        "page": pagination.page,
        "pageSize": pagination.page_size,
        "total": total,
        "hasMore": pagination.offset + len(items) < total,
    }
