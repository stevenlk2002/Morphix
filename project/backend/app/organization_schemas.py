"""组织管理域 Pydantic 模型。

包含组织信息、授权用户、角色的请求/响应 schema。
P0 阶段使用 dict 内存存储 + 种子数据兜底。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field


# ---- 组织信息 ----

class OrgInfoResponse(BaseModel):
    org_name: str = Field(..., alias="orgName")
    contact_name: str = Field(..., alias="contactName")
    contact_phone: str = Field(..., alias="contactPhone")

    model_config = {"populate_by_name": True}


class OrgInfoUpdateRequest(BaseModel):
    org_name: Optional[str] = Field(None, alias="orgName")
    contact_name: Optional[str] = Field(None, alias="contactName")
    contact_phone: Optional[str] = Field(None, alias="contactPhone")

    model_config = {"populate_by_name": True}


# ---- 授权用户 ----

class AuthUserResponse(BaseModel):
    id: str
    account: str
    nickname: str
    role: str


class AuthUserCreateRequest(BaseModel):
    account: str
    nickname: str
    role: str


class AuthUserUpdateRequest(BaseModel):
    account: Optional[str] = None
    nickname: Optional[str] = None
    role: Optional[str] = None


# ---- 角色 ----

class RoleResponse(BaseModel):
    id: str
    name: str
    description: str
    color: str  # danger | success | info


class RoleCreateRequest(BaseModel):
    name: str
    description: str = ""
    color: str = "info"


class RoleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


# ---- 内存存储数据类 ----

@dataclass
class OrgInfoStore:
    org_name: str = "Morphix"
    contact_name: str = "谷一莹"
    contact_phone: str = "18054265130"


@dataclass
class AuthUserStore:
    id: str
    account: str
    nickname: str
    role: str


@dataclass
class RoleStore:
    id: str
    name: str
    description: str
    color: str


# ---- 种子数据 ----

SEED_ORG_INFO = OrgInfoStore(
    org_name="Morphix",
    contact_name="谷一莹",
    contact_phone="18054265130",
)

SEED_AUTH_USERS = [
    AuthUserStore(id="auth-1", account="admin@morphix", nickname="谷一莹", role="管理员"),
    AuthUserStore(id="auth-2", account="leader@morphix", nickname="沈墨白", role="团队组长"),
    AuthUserStore(id="auth-3", account="member01@morphix", nickname="陈知夏", role="普通成员"),
    AuthUserStore(id="auth-4", account="member02@morphix", nickname="林晚舟", role="普通成员"),
    AuthUserStore(id="auth-5", account="leader02@morphix", nickname="苏砚清", role="团队组长"),
]

SEED_ROLES = [
    RoleStore(id="role-admin", name="管理员", description="管理员", color="danger"),
    RoleStore(id="role-lead", name="团队组长", description="团队组长", color="success"),
    RoleStore(id="role-member", name="普通成员", description="普通成员", color="info"),
]
