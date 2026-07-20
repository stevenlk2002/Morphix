# PRD：Morphix「运营任务」子功能版面

> 作者：许清楚（产品经理 / software-product-manager-2）
> 日期：2026-07-19
> 依据：原型 `prototype/index.html`（8666-8756 行）+ 现有前后端代码实际
> 范围：左侧一级栏目「运营管理」下属子版面「运营任务」

## 1. 产品目标
1. 统一运营任务入口——群发/机器人定时/朋友圈/特定节点任务集中管理
2. 精细化生命周期管理——类型/启用/运行状态多维度筛选
3. 任务编辑可追溯——参数/对象/时间三 Tab 独立编辑

## 2. 路由
- `/operations/tasks`（任务列表）✅ 已存在
- `/operations/tasks/:id/edit`（编辑页）需新增

## 3. 页面结构
- Banner 区：标题"运营任务" + 描述 + 装饰 SVG
- 筛选栏：搜索框 + 类型下拉(5种) + 启用状态(全部/已启用/已停用) + 运行状态(5态) + 排序下拉(P1) + [创建运营任务]按钮
- 卡片网格：首张虚线创建卡 + 任务卡(类型badge/Switch/名称/渠道/频率/下次运行时间/编辑/运营记录)
- 空态：仅展示创建入口
- 创建向导：4步 Stepper（①类型→②参数→③对象→④时间），Modal 内完成
- 编辑页：独立路由，返回栏 + 三 Tab（参数/对象/时间）

## 4. 数据实体
- `operation_tasks`：id, name, task_type(5种), channel_type, session_type, content_blocks(JSON), hosting_action, run_frequency, run_time, effective_start/end, run_status(5态), enabled, next_run_time, created_at, updated_at
- `operation_task_targets`：id, task_id, target_type(static/dynamic), session_id, filter_rules(JSON)
- `operation_task_logs`(P1)

## 5. 需求池
### P0
- 任务列表 Banner + 筛选(搜索/类型/启用/运行) + 卡片网格 + Switch 开关
- 创建向导 4 步 Stepper
- 编辑页三 Tab + 内容块管理
- 后端 CRUD + 开关 + 目标路由
- 种子 4-5 个任务

### P1
- 排序下拉 / 运行状态徽标 / "..."菜单 / 运营记录 / 任务类型扩至5种 / 多媒体内容块

### P2
- 批量操作 / 动态选择对象 / 类型差异化参数 / 真实调度引擎

## 6. 种子
- 4-5 个任务覆盖不同 type/status/frequency
- 每任务关联 2-5 个 sessions

## 7. 待确认（建议拍板）
1. 任务类型 P0 3种(群发/机器人定时/朋友圈)，特定节点×2放P1
2. 排序下拉 P1 加入
3. 创建走 Modal，编辑走独立路由
4. 运营记录 P0 toast占位，P1真实表
5. P0仅文本内容块，多媒体 P1

## 8. 验收
- UI 与原型 8666-8698 一致
- 创建 4 步走通
- 编辑三 Tab 可切换
- Switch 即时生效
- 种子 4-5 任务可复现
- API 前缀 `/api/operations/`
