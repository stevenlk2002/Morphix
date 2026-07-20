# PRD：Morphix「客户管理」栏目（子功能版面全量）

> 作者：许清楚（产品经理 / software-product-manager）
> 日期：2026-07-19
> 依据：原型 `prototype/index.html`（9537 行）+ 现有前后端代码实际
> 范围：左侧一级栏目「客户管理」下属全部子版面，指导架构设计与前后端开发
> 硬约束（来自任务）：右侧内容严格按 `prototype/index.html` 实现；数据从 DB 获取，缺失用种子数据填充并同步 DB；先不提交 git；「客户管理」为客户档案**主入口/权威来源**，渠道联系人详情（CON）复用同一模型。

---

## 1. 产品目标

1. **统一客户档案主入口**：将分散在渠道会话中的联系人（CON）沉淀为可运营的客户档案（CP），对外提供一致的客户详情视图。
2. **支撑精细化私域运营**：通过客户列表、分组、标签三大能力，让运营人员按渠道/标签/分组快速定位、筛选、批量触达客户。
3. **业务数据闭环**：沟通记录、自定义属性、标签、AI 总结都围绕同一客户聚合，渠道联系人详情与「客户管理」共用 `customer_profiles` 模型，避免双源。

---

## 2. 栏目导航结构与路由建议

原型导航定义位于 `prototype/index.html:2221-2225`：

| 一级 | 子版面（原型 id） | 原型 HTML 行号 | 建议前端路由（沿用现有 `router.tsx`） |
|---|---|---|---|
| 客户管理 | 客户列表 `customer-list` | 8486–8608 | `/customers`（已存在 → `CustomerListPage`） |
| 客户管理 | 客户分组管理 `customer-groups` | 8610–8656 | `/customers/groups`（已存在 → `CustomerGroupsPage`） |
| 客户管理 | 标签管理 `tags` | 8658–8664（渲染见 6863–6879，数据 2202–2206） | `/customers/tags`（已存在 → `TagsPage`） |

- 路由约定与现有 `/channels/...`、`/operations/...` 一致，无需新增顶层约定。
- 现有 `src/router.tsx` 已注册上述三条路由（见 router.tsx:79-81），**路由层无需改动**，仅需重建/补全对应页面与后端 API。

---

## 3. 子版面业务逻辑梳理

### 3.1 客户列表（`customer-list`）— 核心页

**页面目标**：运营人员统一查看并筛选私域客户，快速进入客户详情/发消息/打标签。

**核心用户故事**
- 作为运营，我想按触达渠道/标签/最后沟通时间筛选外部客户，以便定位待跟进人群。
- 作为运营，我想点开任意客户查看其档案、沟通记录、关联渠道，以便在会话中精准服务。
- 作为运营，我想给客户批量打标签 / 开启 AI 总结，以便后续 SOP 精准触达。

**核心数据实体与字段**（来自原型表格列与行数据 8533-8544）
- 行数据属性：`data-name`、`data-account`（如 `竹绿-健康@医林通`）、`data-channel`（如 `微信`）。
- 外部客户表格列（8533）：`客户名 | 所属私域账号 | 是否开启AI总结 | 最后沟通时间 | 最后沟通记录 | 添加时间 | 标签 | 备注 | 操作`
- 内部成员表格列（8573）：`内部成员 | 所属渠道`（仅两列，数据来自 `channel_contacts.type='internal'`）

**关键交互**
- Tabs：`外部客户` / `内部成员`（`switchCustomerTab`，8489-8490）。
- 搜索框（84894）+ `触达渠道`下拉（8495-8509，分组：企业微信/微信/WhatsApp 各含子账号与「全选」）。
- `更多筛选`气泡（8511-8525）：最后沟通时间(日期区间)、距上次沟通天数(1/3/7天内+自填)、最后沟通记录(文本)、添加时间(日期区间)、已添加日期(1/3天内+自填)、标签(或关系/且关系+选择)、备注、区域、年龄(18-30/31-40+自填)、生日(日期区间)。
- `重置` / `搜索` 按钮；`名片导入` 按钮（8528 → `openCardImportModal`，6890-6907）。
- 跨页全选（8530 `customerSelectAll`）；表格行点击 → `onCustomerRowClick` → `openCustomerDrawer(name, account, channel)`（6936-6939, 6946-6968）。
- 分页：第 1-10 条/共 271 条；页码；10/20/50 条每页（8548-8562）。
- 操作列按钮文案为「客户背面」（8543 等，`customer-op`），实为打开客户详情抽屉——建议 UI 上更名为「详情」。

#### 3.1.1 客户详情抽屉（权威客户档案，隶属客户列表）

> 这是「客户管理」作为**客户档案主入口/权威来源**的核心载体，渠道联系人详情（CON）必须复用此同一数据模型（见 §5 复用关系）。

**结构（`customerDetailDrawerHTML`，5561-5626 + `openCustomerDrawer` 6946-6969）**
- Header：头像、客户名、[+添加标签]（`openCustomerTagModal`）、`账号 · 渠道`、关闭。
- Main 区：
  - 备注（可编辑 `editCustomerNote`，5650-5675，maxlength 1000）。
  - 基本信息（可编辑 `editCustomerInfo`，5676-5719）：`电话 / 邮箱 / 公司 / 职位 / 区域 / 年龄 / 出生日期 / 添加时间`。
  - Tabs：`沟通记录（N）` / `历史备注（N）`；[+添加新的沟通记录]（`openAddCommunicationModal` 5721-5750）。
  - 沟通记录项：日期 + `AI总结` 徽标 + 内容（含优先级 ol / 待办）。
- Side 区：
  - 关联私域渠道：`渠道类型 / 昵称 / 个性签名 / 关联渠道账号 / 渠道备注 / 关联会话`（单聊=客户名；群聊=群名(人数)）。
  - 自定义属性：[+新建]（`openCustomAttributeModal` 5751-5776），以 name/value 行展示。
- Footer：[关闭]、[发消息]（跳转 `channel-sessions` 并打开该客户会话，`sendMessageToContact` 5906-5915）。

**标签弹窗（`openCustomerTagModal`，5628-5649）**：搜索框 + [标签管理]跳转；`全部标签组（3）`；每个标签组标题带 `热标签` 徽标 + 可选标签（点击 toggle `selected`）；[清除已选择标签]；[确定] 保存。

### 3.2 客户分组管理（`customer-groups`）

**页面目标**：查看/管理客户分组（系统或自定义），作为运营任务/SOP 的投放对象。

**核心用户故事**
- 作为运营，我想查看某分组的客户数与维护信息，以便评估分组有效性。
- 作为运营，我想按名称/类型筛选分组，以便快速定位。

**列与筛选（8610-8656）**
- 顶部提示：`新建客户分组请前往「客户列表」进行选择后，保存客户分组`（8612）。**本页无新建按钮**——分组由客户列表勾选客户后保存生成。
- 筛选：客户分组（名称输入）、类型（system/custom）、重置、查询（8613-8629）。
- 表格列：`客户分组 | 类型 | 当前客户数 | 创建时间 | 编辑时间 | 编辑人`（8634-8641）。
- 空态：文件夹图标 + 「暂无数据」（8645-8651）。

### 3.3 标签管理（`tags`）

**页面目标**：维护「标签组 → 标签」二级结构，供客户列表筛选与客户打标签复用。

**核心用户故事**
- 作为运营，我想新建标签组并批量录入标签，便于在客户列表按标签筛选。
- 作为运营，我想编辑/删除标签组与组内标签，保持标签体系干净。

**数据与交互**
- 种子数据 `tagGroups`（2202-2206）：
  - 沟通阶段：`未沟通 / 单方沟通 / 沟通中 / 沟通中自定义`
  - 意向程度：`高 / 中 / 低`
  - 满意度：`非常满意 / 满意 / 一般 / 不满意 / 非常不满意`
- 列表渲染（`renderTagsPage` 6863-6879）：每个 `tag-group-item` = 组标题（名称 + `热标签` 徽标）+ 标签徽标列表 + [编辑]。
- 新建标签组弹窗（`openCreateTagGroupModal` 6800-6813）：`标签组名称` + 多行 `标签`（增/删行，`addTagInputRow` 6834-6842）→ `saveTagGroup` → 重渲染。
- 编辑标签组（`openEditTagGroupModal` 6815-6832）：改名称与标签。

---

## 4. 现有代码缺口分析

### 4.1 前端（`src/pages/Customers/`）

| 文件 | 现状 | 与原型差距 |
|---|---|---|
| `CustomerList.tsx` | **占位 stub**：通用「客户管理」表，列=客户/渠道/等级/标签/累计订单/最近联系，MOCK 数据，无抽屉、无筛选、无分页 | **完全不符**，需按 3.1 重写（列表+筛选+分页+抽屉+标签弹窗+编辑/沟通/属性）。 |
| `Groups.tsx` | **高度对齐**：列、筛选、提示、空态、MOCK+`USE_MOCK` 开关齐备；注释已注明后端 `/api/customer-groups` 尚未提供 | 仅缺真实后端 API 与数据绑定；结构可直接复用。 |
| `Tags.tsx` | 已实现标签组 CRUD（`TagGroup{id,name,color,tags:Tag[]}`），MOCK+`USE_MOCK` | 数据模型比原型更重（带 color/id）；需对齐原型「组→标签」且与后端分组模型统一（见 §8）。 |

### 4.2 后端（`project/backend/app/`）

**已具备（来自「渠道会话」任务，可直接复用）**
- 表：`channel_contacts`(schema.py:197)、`customer_profiles`(212)、`communication_records`(229)、`custom_attributes`(238)。
- `ChannelMgmtRepository.get_contact_detail(contact_id)`（repositories.py:1275-1297）返回 `{contact, profile, communications, attributes}` —— **正是客户详情抽屉的权威聚合**，CON 已用，客户管理应复用。
- `row_to_customer_profile/communication/custom_attribute/contact`（1111-1146, 1071）字段映射明确。
- 路由 `GET /api/contacts`、`GET /api/contacts/{id}`（channel_mgmt.py:59-73）已存在。
- 标签：`customer_tags` 表(schema.py:53，字段 id/name UNIQUE/color/rule) + `TagRepository`(194-221) + `routers/tags.py`（GET/POST/PUT/DELETE `/api/customer-tags`）。

**缺口（需新增/扩展）**
1. **客户列表聚合 API**：现有 `list_contacts` 仅返回基础字段，无 profile/最新沟通/标签/AI总结开关。需新增 `list_customers`（JOIN `channel_contacts`+`customer_profiles`+最新 `communication_records`+标签，支持 type/account/channel/关键字/日期/标签筛选、分页），并暴露路由（建议 `GET /api/customers` 或在 channel_mgmt 扩展）。
2. **`customer_profiles.ai_summary_enabled`**：原型「是否开启AI总结」开关无存储字段，需新增（INTEGER 0/1，默认 0）。
3. **档案更新 API**：原型有「编辑备注/编辑基本信息」，现有仅 GET 详情。需 `PUT /api/contacts/{id}/profile`（更新 phone/email/company/position/region/age/birthday/remark/ai_summary_enabled 等）。
4. **沟通记录新增 API**：`POST /api/customers/{id}/communications`（content/type），需新建仓储方法。
5. **自定义属性新增 API**：`POST /api/customers/{id}/attributes`（name/value）。
6. **客户标签关系**：`customer_tags` 表无「客户→标签」关联。需新增 `customer_tag_relations(customer_id, tag_id)` 及打标签/读取 API（PUT/GET）。
7. **客户分组表与 API**：完全缺失。需 `customer_groups(id, name, type, count, created_at, updated_at, editor)` + `customer_group_members(group_id, customer_id)` + `GET /api/customer-groups` 等。
8. **标签分组模型**：原型为「组→标签」层级，`customer_tags` 为扁平。需新增 `customer_tag_groups(id, name, is_hot)` 并在 `customer_tags` 增加 `group_id`，或建立等效层级（见 §8 待确认）。

### 4.3 数据模型复用关系（关键）

```
channel_contacts (type=customer/internal/customer_group/internal_group)
      │  1:1
      ▼
customer_profiles (phone/email/company/position/region/age/birthday/remark/
                    add_time/add_channel/signature  + 新增 ai_summary_enabled)
      │  1:N                          │  1:N
      ▼                              ▼
communication_records           custom_attributes
(customer_id→profile.id)        (customer_id→profile.id)
      │
      └─ 标签：customer_tags + customer_tag_relations(customer_id, tag_id)
分组：customer_groups + customer_group_members
```
- 「客户管理」详情抽屉 ≡ 渠道联系人详情（CON）共用 `GET /api/contacts/{id}` 聚合，禁止维护两套模型。

---

## 5. 需求池（按优先级）

### P0（必须实现，对齐原型核心）
- **[客户列表]** 外部/内部 Tabs 切换；搜索框；触达渠道下拉筛选。
- **[客户列表]** 外部客户表格 9 列、内部成员 2 列，与 8533/8573 完全一致。
- **[客户列表]** 行点击打开客户详情抽屉（3.1.1 全结构：备注/基本信息/沟通记录 Tab/关联渠道/自定义属性）。
- **[客户列表]** 抽屉内：编辑备注、编辑基本信息、+沟通记录、+自定义属性、+添加标签（弹窗）、发消息跳转。
- **[客户列表]** 「是否开启AI总结」开关（绑定 `ai_summary_enabled`）。
- **[客户列表]** 分页（10/20/50，页码），跨页全选。
- **[标签管理]** 标签组列表展示（组名+标签+编辑）、新建标签组（名称+多标签）、编辑标签组。
- **[客户分组管理]** 列表 + 名称/类型筛选 + 空态（前端 Groups.tsx 已基本就绪，仅需接后端）。
- **[后端]** `GET /api/customers`（聚合列表+筛选+分页）、`GET /api/contacts/{id}`（复用）、`PUT /api/contacts/{id}/profile`、`POST` 沟通记录/自定义属性、标签关系读写、`GET/POST/PUT/DELETE /api/customer-groups`、标签分组模型。
- **[数据]** 种子：扩展 `customer_profiles`（含 `ai_summary_enabled`）、`communication_records`、`custom_attributes`、`customer_tags`（对齐原型 3 组）、`customer_tag_relations`、`customer_groups`、`customer_group_members`。

### P1（重要交互）
- **[客户列表]** `更多筛选` 气泡全部字段（最后沟通时间/距上次沟通天数/添加时间/已添加日期/标签关系/区域/年龄/生日等，8513-8522）。
- **[客户列表]** `名片导入` 弹窗（6890，上传 UI 先 mock，不接 OCR）。
- **[客户列表]** 最后沟通记录上的 `AI总结` popover（8535）。
- **[客户列表]** 标签弹窗「清除已选择标签」「热标签」徽标、搜索（5628-5648）。
- **[客户列表]** 历史备注 Tab 渲染。
- **[客户分组管理]** 从客户列表勾选客户 → 保存为分组的创建流程（原型提示 8612）。
- **[标签管理]** 删除标签组（含组内标签级联）、标签层级与「热标签」标识。

### P2（增强）
- **[客户列表]** 批量打标签、批量操作工具条、导出。
- **[客户分组]** 分组详情（成员列表）、编辑人/编辑时间回填真实值。
- **[标签]** `rule` 字段语义落地（标签命中规则，用于 SOP/筛选）。
- **[名片导入]** 真实 OCR 识别姓名/电话/公司自动建客户（业务闭环外，后置）。
- 客户等级/价值分层（原 stub 有 等级/VIP，原型未体现，慎加，见 §6 Q6）。

---

## 6. UI 设计稿要点（对齐原型行号）

### 6.1 客户列表
- 整体 `.card.customer-list` > `.card-body`（8486）。
- Tabs：`.tabs > .tab.active[data-tab=external]`（8488-8491）。
- Filter bar：搜索(input 180px) + `触达渠道`(import-select，8495-8509) + `更多筛选`(button+popover，8510-8525) + 重置/搜索 + `名片导入`(右对齐，8528)。
- 跨页全选行（8530）；表格 `.table` 表头 9 列（8533）；行 `.customer-name-cell`（头像+name+note）、`.customer-channel`、`.switch`(AI总结)、`.customer-last-msg.has-summary`(AI总结 popover)、`.customer-op`(客户背面→详情)。
- 分页 `.customer-pagination`：条数统计 + 页码 + 每页条数 select（8548-8562）。
- 内部成员：`.customer-member-cell`（头像+name）、`.customer-channel`（8573-8594）。

### 6.2 客户详情抽屉
- `.drawer` > header(头像+title+添加标签+subtitle+close) + body(`.customer-detail-wrap` = main + side) + footer(关闭/发消息)（6948-6967）。
- Main：备注行(编辑) → 基本信息区块(电话/邮箱/公司/职位/区域/年龄/出生日期/添加时间，每项 `contacts-detail-row`) → Tabs(沟通记录(N)/历史备注(N)) + 添加按钮 → `.customer-comm-list`（date + `customer-comm-ai` + content）。
- Side：关联私域渠道区块(渠道类型/昵称/个性签名/关联渠道账号/渠道备注/关联会话 单聊+群聊) + 自定义属性区块(+新建 / name-value 行)。

### 6.3 客户分组管理
- `.card.customer-groups`；`.group-tip`(跳转客户列表)；`.filter-row`(客户分组输入 + 类型 select + 重置/查询)；`.table` 6 列；空态 `.group-empty`(folder 图标 + 暂无数据)。

### 6.4 标签管理
- `.card` > `.card-header`(标题 + 添加标签组按钮) > `.card-body#tagsPageContainer`。
- 列表项 `.tag-group-item`：`.tag-group-title`(名称 + `badge-hot` 热标签) + `.tag-group-tags`(badge 列表) + [编辑]。
- 弹窗：标签组名称 + 多行标签输入(增删行)。

---

## 7. 数据需求与种子方案

**需新增/扩展的表**
1. `customer_profiles` 增加 `ai_summary_enabled INTEGER DEFAULT 0`。
2. `customer_tag_groups(id TEXT PK, name TEXT, is_hot INTEGER DEFAULT 0, created_at)`（新增）。
3. `customer_tags` 增加 `group_id TEXT`（关联 `customer_tag_groups`）。
4. `customer_tag_relations(customer_id TEXT, tag_id TEXT)`（新增，联合主键）。
5. `customer_groups(id, name, type, count, created_at, updated_at, editor)`（新增）。
6. `customer_group_members(group_id, customer_id)`（新增）。

**种子量级建议**
- `customer_profiles`：当前已 seed 5 条；建议扩展到 **~30 个外部客户档案**（原型显示 271 为占位，按真实可运营量级 seed 30，使分页 10/20/50 有意义），覆盖现有 7 个 `channel_contacts` 客户 + 新增约 23 个。
- `communication_records`：每客户 1-3 条（含 `ai_summary`），原型列表「最后沟通记录」取最新一条。
- `custom_attributes`：每客户 0-2 条（如 客户等级=VIP）。
- `customer_tag_groups` + `customer_tags`：严格按原型 3 组 12 个标签（沟通阶段4/意向程度3/满意度5）seed；「热标签」徽标可给全部组 `is_hot=1`（原型渲染对所有组显示）。
- `customer_tag_relations`：为 ~10 个客户关联 1-3 个标签。
- `customer_groups`：seed 4 组（高意向客户/system、618大促触达/custom、沉睡唤醒/custom、复购潜力/system），与 `Groups.tsx` Mock 一致；`customer_group_members` 各关联若干客户。
- 注意：`customer_tags.name` 当前为 UNIQUE，新增分组模型后需解除唯一或改为 (group_id, name) 唯一。

---

## 8. 待确认问题（含与 CON 共用模型）

建议架构师/主理人对以下问题拍板（不要回退给 PM）：

1. **标签分组模型如何落地**：原型为「组→标签」两级且有「热标签」徽标；后端 `customer_tags` 扁平（name UNIQUE/color/rule，无组）。建议新增 `customer_tag_groups` 并在 `customer_tags` 加 `group_id`，`is_hot` 作为可选标志。
2. **「是否开启AI总结」存储**：建议在 `customer_profiles` 新增 `ai_summary_enabled`（INTEGER 0/1）。确认默认值与开关语义。
3. **客户分组创建流程范围**：原型提示分组「从客户列表勾选后保存」生成，本页无新建按钮。P0 是否要求实现「列表勾选→保存分组」完整链路，还是 P0 仅交付分组列表+后端 API、创建流程放 P1？
4. **最后沟通时间/记录来源**：建议取 `communication_records` 最新一条的 `created_at`/`content`(或 `ai_summary`)；若无沟通记录则回退 `channel_contacts.add_time`。确认该优先级。
5. **内部成员是否纳入客户管理**：原型客户列表含「内部成员」Tab（type='internal'）。确认内部成员也走同一详情抽屉（其档案字段可能为空，需空态处理）。
6. **客户等级/价值分层**：原 `CustomerList.tsx` stub 有 等级(VIP/会员/普通)、累计订单，但原型客户列表**无此列**。建议以原型为准，不引入等级分层。
7. **「客户背面」按钮文案**：原型操作列写「客户背面」，实为打开详情。建议前端统一为「详情」。
8. **名片导入**：原型为上传弹窗（6890）。P0 仅做 UI 占位 + mock 提交，真实 OCR 建客户放 P2。
9. **复用确认**：客户详情抽屉与渠道联系人详情（CON）共用 `GET /api/contacts/{id}` 聚合，客户管理不再自建详情接口。

---

## 9. 验收要点（建议）
- 三个子版面 UI 与 §6 行号所引原型结构一致；客户列表 9 列表头/顺序与 8533 完全一致。
- 客户详情抽屉字段覆盖 §3.1.1，且与 CON 同源（改一处两处同步）。
- 所有列表/详情数据来自 DB（非 MOCK），刷新后保留；种子数据已入库且可复现（初始化幂等）。
- 后端新增 API 路径遵循 `/api/...` 约定（见 routers/__init__.py:34 `prefix="/api"`）。
