"""组织管理路由。

端点：
- GET    /org/info              → 获取组织信息
- PUT    /org/info              → 更新组织信息
- GET    /org/auth-users        → 授权用户列表（?account=&nickname= 筛选）
- POST   /org/auth-users        → 新增授权用户
- PUT    /org/auth-users/{id}   → 更新授权用户
- DELETE /org/auth-users/{id}   → 删除授权用户
- GET    /org/roles             → 角色列表（?keyword= 搜索）
- POST   /org/roles             → 新增角色
- PUT    /org/roles/{id}        → 更新角色
- DELETE /org/roles/{id}        → 删除角色

P0 阶段：dict 内存存储 + 种子数据兜底。
"""
from __future__ import annotations

import copy
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..organization_schemas import (
    AuthUserCreateRequest,
    AuthUserResponse,
    AuthUserStore,
    AuthUserUpdateRequest,
    OrgInfoResponse,
    OrgInfoStore,
    OrgInfoUpdateRequest,
    RoleCreateRequest,
    RoleResponse,
    RoleStore,
    RoleUpdateRequest,
    SEED_AUTH_USERS,
    SEED_ORG_INFO,
    SEED_ROLES,
)

router = APIRouter(prefix="/org", tags=["organization"])

# ---- 内存存储 ----

_org_info = OrgInfoStore(
    org_name=SEED_ORG_INFO.org_name,
    contact_name=SEED_ORG_INFO.contact_name,
    contact_phone=SEED_ORG_INFO.contact_phone,
)
_auth_users: list[AuthUserStore] = [copy.deepcopy(u) for u in SEED_AUTH_USERS]
_roles: list[RoleStore] = [copy.deepcopy(r) for r in SEED_ROLES]


# ---- 组织信息 ----

@router.get("/info", response_model=OrgInfoResponse)
async def get_org_info():
    """获取组织信息。"""
    return OrgInfoResponse(
        orgName=_org_info.org_name,
        contactName=_org_info.contact_name,
        contactPhone=_org_info.contact_phone,
    )


@router.put("/info", response_model=OrgInfoResponse)
async def update_org_info(body: OrgInfoUpdateRequest):
    """更新组织信息。"""
    if body.org_name is not None:
        _org_info.org_name = body.org_name
    if body.contact_name is not None:
        _org_info.contact_name = body.contact_name
    if body.contact_phone is not None:
        _org_info.contact_phone = body.contact_phone
    return OrgInfoResponse(
        orgName=_org_info.org_name,
        contactName=_org_info.contact_name,
        contactPhone=_org_info.contact_phone,
    )


# ---- 授权用户 ----

def find_auth_user(user_id: str) -> Optional[dict]:
    """按 id 查找授权用户（供 channel_mgmt 解析团队成员冗余字段）。

    返回 ``{id, account, nickname, role}``；用户不存在时返回 ``None``。
    解析失败不抛错（channel_mgmt 侧据此跳过该用户）。
    """
    for u in _auth_users:
        if u.id == user_id:
            return {
                "id": u.id,
                "account": u.account,
                "nickname": u.nickname,
                "role": u.role,
            }
    return None


@router.get("/auth-users", response_model=list[AuthUserResponse])
async def list_auth_users(
    account: Optional[str] = Query(None),
    nickname: Optional[str] = Query(None),
):
    """授权用户列表，支持按登录账号 / 用户昵称筛选。"""
    result = _auth_users
    if account:
        acc_lower = account.lower()
        result = [u for u in result if acc_lower in u.account.lower()]
    if nickname:
        nick_lower = nickname.lower()
        result = [u for u in result if nick_lower in u.nickname.lower()]
    return [
        AuthUserResponse(id=u.id, account=u.account, nickname=u.nickname, role=u.role)
        for u in result
    ]


@router.post("/auth-users", response_model=AuthUserResponse)
async def create_auth_user(body: AuthUserCreateRequest):
    """新增授权用户。"""
    new_id = f"auth-{uuid.uuid4().hex[:8]}"
    user = AuthUserStore(
        id=new_id,
        account=body.account.strip(),
        nickname=body.nickname.strip(),
        role=body.role.strip(),
    )
    _auth_users.append(user)
    return AuthUserResponse(id=user.id, account=user.account, nickname=user.nickname, role=user.role)


@router.put("/auth-users/{user_id}", response_model=AuthUserResponse)
async def update_auth_user(user_id: str, body: AuthUserUpdateRequest):
    """更新授权用户。"""
    for i, u in enumerate(_auth_users):
        if u.id == user_id:
            if body.account is not None:
                _auth_users[i].account = body.account.strip()
            if body.nickname is not None:
                _auth_users[i].nickname = body.nickname.strip()
            if body.role is not None:
                _auth_users[i].role = body.role.strip()
            u2 = _auth_users[i]
            return AuthUserResponse(
                id=u2.id, account=u2.account, nickname=u2.nickname, role=u2.role
            )
    raise HTTPException(status_code=404, detail="授权用户不存在")


@router.delete("/auth-users/{user_id}", response_model=dict)
async def delete_auth_user(user_id: str):
    """删除授权用户。"""
    for i, u in enumerate(_auth_users):
        if u.id == user_id:
            _auth_users.pop(i)
            return {"deleted": True, "id": user_id}
    raise HTTPException(status_code=404, detail="授权用户不存在")


# ---- 角色 ----

@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(keyword: Optional[str] = Query(None)):
    """角色列表，支持按名称搜索。"""
    result = _roles
    if keyword:
        kw = keyword.strip()
        result = [r for r in result if kw in r.name]
    return [
        RoleResponse(id=r.id, name=r.name, description=r.description, color=r.color)
        for r in result
    ]


@router.post("/roles", response_model=RoleResponse)
async def create_role(body: RoleCreateRequest):
    """新增角色。"""
    new_id = f"role-{uuid.uuid4().hex[:8]}"
    role = RoleStore(
        id=new_id,
        name=body.name.strip(),
        description=body.description.strip(),
        color=body.color.strip(),
    )
    _roles.append(role)
    return RoleResponse(id=role.id, name=role.name, description=role.description, color=role.color)


@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(role_id: str, body: RoleUpdateRequest):
    """更新角色。"""
    for i, r in enumerate(_roles):
        if r.id == role_id:
            if body.name is not None:
                _roles[i].name = body.name.strip()
            if body.description is not None:
                _roles[i].description = body.description.strip()
            if body.color is not None:
                _roles[i].color = body.color.strip()
            r2 = _roles[i]
            return RoleResponse(
                id=r2.id, name=r2.name, description=r2.description, color=r2.color
            )
    raise HTTPException(status_code=404, detail="角色不存在")


@router.delete("/roles/{role_id}", response_model=dict)
async def delete_role(role_id: str):
    """删除角色。"""
    for i, r in enumerate(_roles):
        if r.id == role_id:
            _roles.pop(i)
            return {"deleted": True, "id": role_id}
    raise HTTPException(status_code=404, detail="角色不存在")
