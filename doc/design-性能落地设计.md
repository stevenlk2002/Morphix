# Morphix 性能落地设计文档

**版本**: 0.1.0  
**日期**: 2026-07-17  
**作者**: Crow5 (NZSK 科技研发)

---

## 1. 目标与背景

根据架构报告 `report-原型驱动需求理解与初步架构建议.md`，Morphix 系统的性能规划目标为：

- **规模目标**: 支持 1000 渠道账号在线，每账号 1000+ 联系人/群，同时支持托管与运营任务
- **延迟目标**: 主回复 P99 < 3 秒
- **架构路线**: 控制面模块化单体 + 执行面事件驱动拆分 + 设备面独立演进
- **MVP 阶段**: 先保证「控制面先跑通 1v1 托管 + 编排」，基础设施保持 SQLite，预留可切换能力

本文档定义 MVP 阶段（当前实施）的性能落地策略与后续升级路径。

---

## 2. 分阶段性能策略

### 2.1 MVP 阶段（当前）

**核心目标**: 控制面可观测 + 数据访问规范化，为后续升级打好地基。

#### 已实施能力

| 能力 | 实现方式 | 代码位置 |
|------|----------|----------|
| **数据访问层抽象** | `DatabaseBackend` 协议 + SQLite 实现，预留 PostgreSQL 接口 | `app/database.py` |
| **分页规范** | `Pagination` + `normalize_pagination` + `paginate_result` 统一信封 | `app/pagination.py` |
| **索引定义** | 高频查询列建立复合索引（bots / channels / tags / workflow_nodes） | `app/schema.py` |
| **P99 埋点** | `MetricsMiddleware` 记录请求耗时，按路由模板聚合分位数 | `app/observability.py` |
| **增强健康检查** | `/api/health` 检测数据库连通性 + 返回数据库路径 | `app/routers/meta.py` |
| **指标暴露** | `/api/metrics` 输出全局 + 各路由 P50/P95/P99/max | `app/routers/meta.py` |

#### 技术栈与容量

- **数据库**: SQLite（WAL 模式提升并发读性能）
- **连接池**: 线程局部连接（贴合 FastAPI 线程池模型）
- **预期 QPS**: 控制面 < 100 QPS（管理后台主要是读操作）
- **存储容量**: 单文件数据库，适配 < 10 万条配置/审计记录
- **并发**: 单进程单线程池，适配小规模团队（< 50 并发管理操作）

#### 边界与限制

- **不支持高并发写入**: SQLite 写锁全库，高并发写会串行化
- **不支持跨节点扩展**: 单文件无法水平扩展
- **无缓存层**: 热数据无 Redis 缓存，高频查询直接打 DB
- **无消息队列**: 异步任务（标签分析/运营触达）尚未解耦

**适用场景**: 控制面 MVP，10 人以内团队使用，配置变更频率低。

---

### 2.2 Beta 阶段（下一步）

**核心目标**: 执行面独立 + 引入缓存与索引加速，支持 100 账号在线 + 并发会话 1000 级。

#### 升级路径

| 模块 | 当前 | Beta 目标 | 升级方式 |
|------|------|----------|----------|
| **数据库** | SQLite | PostgreSQL 12+ | 实现 `PostgresBackend`，替换 `build_backend` 工厂分支，Repository 层零改动 |
| **缓存** | 无 | Redis 6+ | 热数据（bot / channel / workflow）加缓存层，TTL 5-10 分钟 |
| **知识检索** | 无 | pgvector | 向量化知识库，支持语义检索 + 相似度排序 |
| **会话状态** | 静态 | Redis Hash | 会话热状态（当前托管 bot / 人工接管状态）迁移到 Redis |
| **异步任务** | 同步 | Celery + Redis | 标签分析 / 客户画像 / SOP 触达异步化，不阻塞主链路 |

#### 容量目标

- **并发会话**: 1000 级
- **控制面 QPS**: < 500 QPS
- **执行面 QPS**: < 5000 QPS（会话消息 + Agent 执行）
- **P99 延迟**: 控制面 < 500ms，执行面 < 3s

#### 数据库迁移要点

1. **占位符翻译**: PostgreSQL 用 `%s`，SQLite 用 `?`，需在 `PostgresBackend` 实现中翻译
2. **事务隔离**: PostgreSQL 默认 Read Committed，需显式设置 Repeatable Read（若需）
3. **AUTOINCREMENT 差异**: PostgreSQL 用 SERIAL / BIGSERIAL，建表语句需调整
4. **索引策略**: PostgreSQL 支持部分索引 + GIN/GIST，可针对 JSON 字段建索引
5. **连接池**: 引入 `psycopg2-pool` 或 `asyncpg`，替换线程局部连接

---

### 2.3 Phase 2（规模化阶段）

**核心目标**: 支持 1000 账号在线 + 并发会话 1 万级 + 分区分片 + 多区域调度。

#### 架构演进

| 能力 | 实现方式 |
|------|----------|
| **数据库分片** | 按 project_id 分片（每个项目独立 schema 或独立 PG 实例） |
| **读写分离** | PG 主从 + pgpool / HAProxy 读写路由 |
| **消息总线** | Kafka 替代 Redis，支持重放 + 持久化 + 多消费者 |
| **执行面水平扩展** | 工作流运行时 + Agent 执行器 部署多副本，无状态设计 |
| **设备集群治理** | 设备网关按地域分组，指令下发路由到最近网关 |
| **数据湖** | 会话日志 / 审计事件 归档到 ClickHouse / S3，支持离线分析 |

#### 容量目标

- **渠道账号**: 1000+
- **并发会话**: 1 万+
- **控制面 QPS**: < 2000 QPS
- **执行面 QPS**: < 5 万 QPS
- **P99 延迟**: 控制面 < 500ms，执行面 < 3s

---

## 3. 数据访问层抽象设计

### 3.1 接口定义

所有数据访问统一走 `DatabaseBackend` 协议：

```python
class DatabaseBackend(Protocol):
    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict]: ...
    def query_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[dict]: ...
    def execute(self, sql: str, params: Sequence[Any] = ()) -> int: ...
    def executescript(self, script: str) -> None: ...
    @contextmanager
    def transaction(self) -> Iterator["DatabaseBackend"]: ...
```

### 3.2 切换 PostgreSQL 步骤

1. **实现 `PostgresBackend`**（参考 `SQLiteBackend`）
2. **占位符翻译**: `?` → `%s`
3. **注册到工厂**: `build_backend` 中增加 `if settings.db_backend == "postgres"` 分支
4. **环境变量配置**: 设置 `MORPHIX_DB_BACKEND=postgres` + `MORPHIX_POSTGRES_DSN=postgresql://...`
5. **迁移数据**: 导出 SQLite 数据，导入 PostgreSQL（工具：`pgloader` 或自定义脚本）
6. **验证**: 运行全量测试，确保 API contract 不变

### 3.3 Repository 层规范

- **单一职责**: 一个 Repository 对应一张或一组相关表
- **无业务逻辑**: Repository 只负责 CRUD + DTO 转换，不含业务判断
- **事务边界**: 事务由 Router 层控制，Repository 只接收 backend 参数
- **分页统一**: 列表查询统一返回 `(items, total)` 元组，由 Router 包装成分页信封

---

## 4. 分页与索引规范

### 4.1 分页规范

所有列表查询必须支持分页，避免无界返回：

```python
def list_paged(page: int = 1, pageSize: Optional[int] = None):
    pagination = normalize_pagination(page, pageSize)
    items, total = repository.list_paged(pagination)
    return paginate_result(items, total, pagination)
```

**统一信封格式**:

```json
{
  "items": [...],
  "page": 1,
  "pageSize": 20,
  "total": 45,
  "hasMore": true
}
```

### 4.2 索引策略

| 表 | 索引列 | 查询场景 |
|---|--------|----------|
| `bots` | `(created_at, id)` | 分页排序 |
| `bots` | `(project)` | 按项目过滤 |
| `bots` | `(status)` | 按状态筛选 |
| `channel_accounts` | `(created_at, id)` | 分页排序 |
| `channel_accounts` | `(status)` | 按状态筛选 |
| `customer_tags` | `(created_at, id)` | 分页排序 |
| `workflow_nodes` | `(workflow_id, node_order)` | 按流程查节点 + 排序 |
| `audit_events` | `(created_at)` | 时间范围查询 |

**索引原则**:
- 高频查询列（WHERE / ORDER BY）必建索引
- 复合索引左前缀匹配（`(workflow_id, node_order)` 可支持 `WHERE workflow_id = ?` 或 `WHERE workflow_id = ? ORDER BY node_order`）
- 避免过度索引（写入会变慢，存储会增加）

---

## 5. P99 可观测性设计

### 5.1 埋点机制

通过 `MetricsMiddleware` 中间件，每个请求记录耗时（毫秒），按路由模板聚合：

```python
class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        route = _route_template(request)  # 如 "GET /api/bots"
        metrics_store.record(route, duration_ms, is_error)
        if duration_ms > settings.slow_request_ms:
            logger.warning("slow request %s took %.1fms", route, duration_ms)
        return response
```

### 5.2 指标聚合

每个路由维护滑动窗口（最近 500 个样本），实时计算分位数：

```python
{
  "slowRequestThresholdMs": 3000.0,
  "overall": {"count": 100, "errors": 0, "p50": 12.3, "p95": 45.6, "p99": 78.9, "max": 120.5},
  "routes": {
    "GET /api/dashboard": {"count": 20, "errors": 0, "p50": 15.2, "p95": 50.1, "p99": 85.3, "max": 120.5},
    "POST /api/bots": {"count": 10, "errors": 0, "p50": 8.7, "p95": 22.3, "p99": 35.6, "max": 40.2}
  }
}
```

### 5.3 慢请求告警

超过阈值（默认 3000ms）的请求打 WARNING 日志：

```
2026-07-17 18:00:12 [WARNING] morphix.perf: slow request GET /api/dashboard took 3200.1ms
```

### 5.4 升级路径

MVP 用进程内内存聚合，零外部依赖；升级时可替换为：

- **Prometheus**: `prometheus-client` + `/metrics` 输出 OpenMetrics 格式
- **OpenTelemetry**: `opentelemetry-instrumentation-fastapi` + 导出到 Jaeger / Tempo
- **APM 工具**: DataDog / New Relic / Elastic APM

---

## 6. 健康检查设计

### 6.1 MVP 版本

```json
GET /api/health
{
  "status": "healthy",
  "service": "morphix-backend",
  "database": "/path/to/morphix_mvp.db"
}
```

检查项：
- 数据库连通性（`SELECT 1`）
- 返回 200 表示健康，500 表示不健康

### 6.2 Beta 版本（扩展）

```json
{
  "status": "healthy",
  "service": "morphix-backend",
  "dependencies": {
    "database": {"status": "healthy", "latency_ms": 2.3},
    "redis": {"status": "healthy", "latency_ms": 0.8},
    "pgvector": {"status": "healthy", "latency_ms": 15.2}
  },
  "disk": {"used_gb": 12.5, "total_gb": 100, "usage_percent": 12.5}
}
```

### 6.3 用途

- **容器编排**: Kubernetes Liveness / Readiness Probe
- **负载均衡**: HAProxy / Nginx 健康检查
- **监控告警**: 定期轮询 `/api/health`，异常时触发告警

---

## 7. 性能测试与验收标准

### 7.1 MVP 阶段验收标准

| 指标 | 目标 | 验证方式 |
|------|------|----------|
| 控制面 P99 | < 500ms | 查看 `/api/metrics`，确保所有路由 P99 < 500ms |
| 数据库响应 | < 50ms | `/api/health` 返回数据库连通性正常 |
| 测试覆盖 | 100% API | `pytest` 全量通过，9/9 测试绿色 |
| 慢请求日志 | 有记录 | 查看日志文件，确保超 3000ms 请求被记录 |

### 7.2 Beta 阶段性能测试

**工具**: Locust / k6 / Apache JMeter

**测试场景**:
- 控制面读操作（dashboard / bots / workflows）: 目标 500 QPS，P99 < 500ms
- 控制面写操作（create bot / update workflow）: 目标 50 QPS，P99 < 1s
- 执行面消息入口: 目标 5000 QPS，P99 < 3s

**验收标准**:
- 所有场景 P99 达标
- 错误率 < 0.1%
- CPU < 70%，内存 < 80%

---

## 8. 成本与资源规划

### 8.1 MVP 阶段（当前）

- **服务器**: 单机 2C4G（本地开发 / 小规模部署）
- **存储**: 10 GB（SQLite 文件 + 日志）
- **成本**: 基本免费（本地 / 内网部署）

### 8.2 Beta 阶段

- **控制面**: 2C4G x 1
- **执行面**: 4C8G x 2（水平扩展）
- **数据库**: PostgreSQL 4C16G + 100GB SSD
- **Redis**: 2C4G + 10GB
- **成本**: 约 $200/月（云服务商）

### 8.3 Phase 2

- **控制面**: 4C8G x 2（主备）
- **执行面**: 8C16G x 5-10（弹性伸缩）
- **数据库**: PostgreSQL 主从 + 分片
- **Redis 集群**: 6 节点
- **消息队列**: Kafka 3 节点
- **成本**: 约 $2000-5000/月

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| SQLite 写锁全库 | 高并发写会串行化，P99 劣化 | Beta 尽早切 PostgreSQL |
| 无缓存层 | 热数据反复查库，DB 压力大 | 引入 Redis 缓存热配置 |
| 单点故障 | 单机宕机全服务不可用 | Beta 引入主备 + 健康检查 |
| 数据丢失 | SQLite 文件损坏 | 定期备份 + WAL 模式 + Beta 切 PG |
| 慢 SQL 未监控 | 性能劣化无感知 | P99 埋点 + 慢请求日志 |

---

## 10. 实施检查清单

### ✅ MVP 阶段（已完成）

- [x] 数据访问层抽象（`DatabaseBackend` 协议）
- [x] SQLite 实现 + WAL 模式 + 线程局部连接
- [x] 分页规范（`Pagination` + `paginate_result`）
- [x] 索引定义（bots / channels / tags / workflow_nodes）
- [x] P99 埋点中间件（`MetricsMiddleware`）
- [x] `/api/health` 增强健康检查
- [x] `/api/metrics` 指标暴露
- [x] 慢请求日志（超 3000ms 打 WARNING）
- [x] 所有现有测试通过（9/9）
- [x] API contract 保持不变

### 🔲 Beta 阶段（待实施）

- [ ] 实现 `PostgresBackend`（占位符翻译 + 连接池）
- [ ] SQLite → PostgreSQL 数据迁移脚本
- [ ] 引入 Redis 缓存层（bot / channel / workflow 热数据）
- [ ] 知识库向量化（pgvector 集成）
- [ ] 会话状态迁移到 Redis Hash
- [ ] 异步任务队列（Celery + Redis）
- [ ] 执行面独立部署（工作流运行时 + Agent 执行器）
- [ ] Locust 性能测试 + 报告
- [ ] 监控告警（Prometheus / Grafana / AlertManager）

### 🔲 Phase 2（待规划）

- [ ] 数据库分片方案设计
- [ ] 消息总线（Kafka）
- [ ] 执行面水平扩展 + 负载均衡
- [ ] 设备集群治理
- [ ] 数据湖（ClickHouse / S3）
- [ ] 多区域调度

---

## 11. 总结

本文档定义了 Morphix 系统从 MVP → Beta → Phase 2 的性能落地路径：

- **MVP 阶段**（当前）：控制面可观测 + 数据访问规范化，SQLite 快速迭代，零外部依赖。
- **Beta 阶段**（下一步）：执行面独立 + PostgreSQL + Redis + 异步任务，支持 100 账号 + 1000 并发会话。
- **Phase 2**（规模化）：分片 + 消息总线 + 水平扩展，支持 1000 账号 + 1 万并发会话。

核心设计原则：**可逆性最高**。数据访问层抽象保证切换数据库时 Repository 层零改动，P99 埋点保证性能劣化可感知，分页规范保证后续扩展无界面改动。

所有性能落地能力（数据访问层抽象 / 分页 / 索引 / P99 埋点 / 健康检查 / 指标暴露）均已在 MVP 阶段实现并通过测试，为后续升级打好地基。
