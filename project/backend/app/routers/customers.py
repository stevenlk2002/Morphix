"""客户管理域路由。

端点：
- GET    /customers                           → 客户列表聚合（筛选+分页）
- GET    /customers/{customer_id}             → 单个客户聚合详情
- POST   /customers/{customer_id}/communications → 新增沟通记录
- POST   /customers/{customer_id}/attributes     → 新增自定义属性
- GET    /customer-tag-relations/{customer_id}   → 获取客户标签
- PUT    /customer-tag-relations/{customer_id}   → 批量设置客户标签
- GET    /customer-tag-groups                    → 标签组列表
- POST   /customer-tag-groups                    → 新建标签组
- PUT    /customer-tag-groups/{id}               → 编辑标签组
- DELETE /customer-tag-groups/{id}               → 删除标签组
- GET    /customer-groups                        → 客户分组列表
- POST   /customer-groups                        → 新建客户分组
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from ..database import get_backend
from ..repositories import ChannelMgmtRepository, CustomerRepository
from ..schemas import (
    AddMembersRequest,
    BatchAiSummaryRequest,
    BatchTagsRequest,
    CommunicationCreateRequest,
    CustomAttributeCreateRequest,
    CustomerGroupCreateRequest,
    CustomerGroupCreateWithMembersRequest,
    CustomerGroupDeleteRequest,
    CustomerTagRelationRequest,
    TagGroupCreateRequest,
    TagGroupUpdateRequest,
)

router = APIRouter(prefix="/customers", tags=["customers"])


# ---- 客户列表 ----

@router.get("")
def list_customers(
    type: Optional[str] = None,
    accountId: Optional[str] = None,
    channel: Optional[str] = None,
    channelType: Optional[str] = None,
    keyword: Optional[str] = None,
    tagIds: Optional[str] = None,  # comma-separated
    dateFrom: Optional[str] = None,
    dateTo: Optional[str] = None,
    page: int = 1,
    pageSize: int = 10,
):
    """客户列表聚合（JOIN contacts+profile+最新沟通+标签，支持筛选+分页）。"""
    tag_id_list = [t.strip() for t in tagIds.split(",") if t.strip()] if tagIds else None
    return CustomerRepository(get_backend()).list_customers(
        type_=type,
        account_id=accountId,
        channel=channel,
        channel_type=channelType,
        keyword=keyword,
        tag_ids=tag_id_list,
        date_from=dateFrom,
        date_to=dateTo,
        page=page,
        page_size=pageSize,
    )


@router.get("/{customer_id}")
def get_customer_detail(customer_id: str):
    """单个客户聚合详情（复用 ChannelMgmtRepository.get_contact_detail）。"""
    # customer_id 即 contact_id（客户管理域 id 即 contact_id）
    return ChannelMgmtRepository(get_backend()).get_contact_detail(customer_id)


# ---- 批量操作（必须在 /{customer_id}/... 之前，防止 "batch" 被当作 customer_id） ----

@router.put("/batch/ai-summary")
def batch_update_ai_summary(payload: BatchAiSummaryRequest):
    """批量更新 AI 总结开关。"""
    updated = CustomerRepository(get_backend()).batch_update_ai_summary(
        payload.contactIds, payload.enabled
    )
    return {"updated": updated}


@router.put("/batch/tags")
def batch_update_tags(payload: BatchTagsRequest):
    """批量操作客户标签（add/remove/replace）。"""
    return CustomerRepository(get_backend()).batch_update_tags(
        payload.contactIds, payload.tagIds, payload.mode
    )


# ---- 沟通记录 ----

@router.post("/{customer_id}/communications")
def create_communication(customer_id: str, payload: CommunicationCreateRequest):
    """新增沟通记录（customer_id = customer_profiles.id 或 contact_id）。"""
    return CustomerRepository(get_backend()).create_communication(
        customer_id, payload.content, payload.type, payload.aiSummary or ""
    )


@router.get("/{customer_id}/communications")
def list_communications(customer_id: str):
    """获取客户沟通记录列表。"""
    return CustomerRepository(get_backend()).list_communications(customer_id)


# ---- 自定义属性 ----

@router.post("/{customer_id}/attributes")
def create_attribute(customer_id: str, payload: CustomAttributeCreateRequest):
    """新增自定义属性。"""
    return CustomerRepository(get_backend()).create_attribute(customer_id, payload.name, payload.value)


# ---- 标签关系 ----

@router.get("/{customer_id}/tags")
def get_customer_tags(customer_id: str):
    """获取客户标签列表。"""
    return CustomerRepository(get_backend()).get_customer_tags(customer_id)


@router.put("/{customer_id}/tags")
def set_customer_tags(customer_id: str, payload: CustomerTagRelationRequest):
    """批量设置客户标签（替换式）。"""
    CustomerRepository(get_backend()).set_customer_tags(customer_id, payload.tagIds)
    return {"ok": True}


# ---- 标签分组（挂载在 customers router 下，也可独立访问） ----

_tag_group_router = APIRouter(prefix="/customer-tag-groups", tags=["tag-groups"])


@_tag_group_router.get("")
def list_tag_groups():
    """标签组列表（含组内标签）。"""
    return CustomerRepository(get_backend()).list_tag_groups()


@_tag_group_router.post("")
def create_tag_group(payload: TagGroupCreateRequest):
    """新建标签组（名称+标签列表）。"""
    return CustomerRepository(get_backend()).create_tag_group(
        payload.name, payload.isHot, payload.tags
    )


@_tag_group_router.put("/{group_id}")
def update_tag_group(group_id: str, payload: TagGroupUpdateRequest):
    """编辑标签组（名称+标签增删改）。"""
    result = CustomerRepository(get_backend()).update_tag_group(
        group_id, payload.name, payload.isHot, payload.tags
    )
    if result is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": "标签组不存在"})
    return result


@_tag_group_router.delete("/{group_id}")
def delete_tag_group(group_id: str):
    """删除标签组（级联删除组内标签+关系）。"""
    ok = CustomerRepository(get_backend()).delete_tag_group(group_id)
    if not ok:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": "标签组不存在"})
    return {"id": group_id, "deleted": True}


# ---- 客户分组 ----

@router.get("/groups/list")
def list_customer_groups_internal(
    name: Optional[str] = None,
    type: Optional[str] = None,
):
    """客户分组列表（筛选）。"""
    return CustomerRepository(get_backend()).list_customer_groups(name, type)


@router.post("/groups")
def create_customer_group_internal(payload: CustomerGroupCreateRequest):
    """新建客户分组。"""
    return CustomerRepository(get_backend()).create_customer_group(
        payload.name, payload.type, payload.customerIds
    )


# ---- 客户分组独立路由（/api/customer-groups） ----
_customer_groups_router = APIRouter(prefix="/customer-groups", tags=["customer-groups"])


@_customer_groups_router.get("")
def list_customer_groups(
    name: Optional[str] = None,
    type: Optional[str] = None,
):
    """客户分组列表（筛选）。"""
    return CustomerRepository(get_backend()).list_customer_groups(name, type)


@_customer_groups_router.post("")
def create_customer_group(payload: CustomerGroupCreateRequest):
    """新建客户分组。"""
    return CustomerRepository(get_backend()).create_customer_group(
        payload.name, payload.type, payload.customerIds
    )


@_customer_groups_router.post("/with-members")
def create_customer_group_with_members(payload: CustomerGroupCreateWithMembersRequest):
    """新建客户分组并添加初始成员（事务）。"""
    return CustomerRepository(get_backend()).create_group_with_members(
        payload.name, payload.type, payload.memberIds
    )


@_customer_groups_router.post("/{group_id}/members")
def add_members_to_group(group_id: str, payload: AddMembersRequest):
    """批量添加成员到已有分组。"""
    result = CustomerRepository(get_backend()).add_members_to_group(group_id, payload.contactIds)
    if result is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": "分组不存在"})
    return result


@_customer_groups_router.get("/{group_id}")
def get_customer_group(group_id: str):
    """获取分组详情（含成员列表，含客户聚合数据）。"""
    result = CustomerRepository(get_backend()).get_group_with_members(group_id)
    if result is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": "分组不存在"})
    return result


@_customer_groups_router.post("/batch-delete")
def batch_delete_customer_groups(payload: CustomerGroupDeleteRequest):
    """批量删除客户分组（事务内级联删除 members）。"""
    deleted = CustomerRepository(get_backend()).delete_groups(payload.group_ids)
    return {"deleted": deleted, "groupIds": payload.group_ids}
