"""统一契约域（移植自 morphix-control，自包含 SQLAlchemy 持久层）。

双库隔离：本包使用独立的 morphix_contract.db，与 project/backend 资源域的
morphix_mvp.db（裸 SQL）互不干扰。本包代码近乎逐字移植 morphix-control，
仅改写 import 路径（app.core.* -> app.contract.*，config 复用后端 app.config）。
"""
from . import database  # 先注册 Base
from . import models  # noqa: F401  注册全部 ORM 表到 Base.metadata
from . import envelope, responses, security, schemas, seed
