# 河马客服 SOP · Morphix 编排 MVP 上线计划（A8 优先）

> 配套文档：
> - [`hema-sop-agent-orchestration.md`](./hema-sop-agent-orchestration.md) — 总体编排设计（17 节点 / 10 智能体 / 合规三道锁）
> - [`hema-sop-agent-prompts.md`](./hema-sop-agent-prompts.md) — 各阶段提示词全文
> - [`hema-sop-morphix-workflow.json`](./hema-sop-morphix-workflow.json) — 已生成的 Morphix 可导入工作流（本计划三期落地后的目标全集）
>
> **铁律：A8 合规守门必须先于任何自动发送能力上线。顺序颠倒 = 裸奔。**

---

## 0. 一句话原则

先把"闸"装上，再放水。A8 合规守门是所有对客文本的**唯一出口**，它不在线时，AI 一律只能"看"不能"说"。

---

## 1. 当前平台能力边界（决定 MVP 形态）

| 能力 | Morphix 现状 | 对 MVP 的影响 |
|---|---|---|
| 节点类型 | `userInput / aiChat / kbSearch / multiJudge / msgOutput / setMorphixTag / setCustomerAttr / interruptBefore/After` | 够用，无原生"合规节点" |
| 合规守门 | **无原生节点**，靠"拓扑唯一出口"约定：画布上除 A8→msgOutput 外的节点不得直连 `msgOutput.message` | A8 必须串在每条对客路径末端 |
| 条件分叉 | 运行时引擎仅走 `nexts[0]` 单分支，**不支持 if/else 分叉** | 路由判断（A0 的派单）当前只能落到"单线主路径 + 并行支线"，分支执行需待引擎升级 |
| 人工在环 | `interruptBefore` / `interruptAfter` 节点（config.wait）即人工审批暂停 | N07/N08/N11/N15 用 `interruptBefore` 实现 |
| 提示词版本 | 无 `prompt_id/version/ab_group` 存储字段 | 暂塞进 `aiChat.config` 自定义 key，待 schema 扩展 |
| RAG | `kbSearch.config.kb` 为纯文本字段，知识库是 QA 对表 | 4 个 KB 以字符串名引用，需先在知识库建好对应表 |

**结论**：一期只能做"单主路径 + 人工在环 + A8 守门"的线性闭环；A0 的全路由派单是目标态，需引擎支持分叉后再扩。

---

## 2. 三期 MVP 范围

### Phase 1 · 合规先行（第 1–2 周）— 最小可运行闭环

**目标**：验证 A8 守门能拦住风险话术，且人工在环可用。零对客自动发送风险。

| 上线 | 节点 | 模式 | 说明 |
|---|---|---|---|
| ✅ A9 标签 | `n_a9` aiChat → `n_tag` setMorphixTag | 纯写库 | 零对客风险，先验证模型对 SOP 第六章标签体系的理解力 |
| ✅ A8 合规守门 | `n_a8` aiChat → `n_judge` → `n_msg` | 守门接管 | **先上线、先接管**。先用一条"演示对客路径"喂样本文本验证拦截率 |
| ✅ A5 成交信号 | `n_a5` aiChat → `n_sc5` setCustomerAttr | 仅看板 | 只给客服提示，不自动发 |

**Phase 1 验收**：拿 SOP 里的违规原话（"久鸣必聋""无效不成药""发现一例虚假…"）做 20 条样本，A8 拦截率 ≥ 95% 才进 Phase 2。

### Phase 2 · 主力 AI 节点（第 3–6 周）— 开自动发送

**前置条件**：A8 已稳定运行且拦截率达标。

| 上线 | 节点 | 模式 | 说明 |
|---|---|---|---|
| ✅ A4 异议应答 | `n_a4` aiChat + `n_kbqa` kbSearch → `n_a8` → 发送 | 副驾→自动 | 一期先"只给客服看"，二期转自动发送；价格疑虑 `route_to_human` 永不让 AI 回价 |
| ✅ A1 破冰触达 | `n_a1` aiChat + `n_kbmed` → `n_a8` → 发送 | 自动 | 仅 D0–D3 未开口客户，D3 后转低频队列 |
| ✅ A2 问诊采集 | `n_a2` aiChat + `n_kbmed` → `n_a8` → 发送 | 自动（最高价值） | 12 槽位逐问；中途提疑虑 `handoff_to: A4` |

**Phase 2 验收**：A1/A2/A4 经 A8 发出的消息 100% 过闸；价格类转人工率、客户回复率进入看板监控。

### Phase 3 · 收口与质检（第 7 周+）— 人工在环 + 离线质检

| 上线 | 节点 | 模式 | 说明 |
|---|---|---|---|
| ✅ A3 病历摘要 | `n_a3` → `n_h3` interruptBefore → `n_sc3` | 人工在环 | **N07 下结论出方案**：AI 产出摘要，必须经 `interruptBefore` 人工确认后才进待办 |
| ✅ A6 沉默唤醒 | `n_a6` → `n_h6` interruptBefore → `n_sc6` | 人工在环 | 起草唤醒文案，人工确认后发 |
| ✅ A7 交接铺垫 | `n_a7` → `n_h7` interruptBefore → `n_sc7` | 人工在环+系统动作 | B3/B5 强制写跟进记录、推交接群 @医助，漏一步工单不关 |
| ✅ A10 会话质检 | 离线批处理 | 离线 | 对已结束会话打分，critical 项单独告警 |

**Phase 3 验收**：5 次铺垫完成率、医助跟进触发率、质检 compliance 维度 0 分项 = 0。

---

## 3. 上线顺序一览（对齐附录 B）

```
Week 1-2   A9 标签  → 纯写库，零对客风险，先验证模型理解力
Week 3-4   A4 异议 + A5 信号  → 副驾模式，只给客服看，不自动发
Week 5-6   A8 合规守门上线并接管全部出口   ← 必须先于自动发送
Week 7-8   A1 破冰 + A2 问诊  → 开自动发送（必须先有 A8）
Week 9+    A3 病历 + A6 唤醒 + A7 交接 + A10 质检
```

> **A8 必须先于任何自动发送能力上线。** 顺序颠倒 = 裸奔。

---

## 4. 导入方式

生成的 `hema-sop-morphix-workflow.json` 是前端画布 `WorkflowPersisted` 格式：

```bash
# 方式 A：REST 导入（botId 替换为实际机器人）
curl -X PUT "http://<host>/api/orchestration/workflows/hema_kefu" \
  -H "Content-Type: application/json" \
  -d @hema-sop-morphix-workflow.json

# 方式 B：编排台 UI → 导出/保存 兼容的 JSON，直接粘贴 nodes/edges
```

也可经 `python3 gen_hema_workflow.py` 重新生成（提示词改动后重跑即可）。

---

## 5. 风险与待办（给研发）

1. **引擎分叉缺失**：A0 全路由派单依赖条件分支，当前引擎单分支。临时方案：每类客户走独立子工作流，A0 仅做"选哪个 bot/子流"的元调度。
2. **A8 非原生节点**：当前靠拓扑约定保证唯一出口。建议研发在引擎层加 `policy` 节点强校验：任何 `msgOutput` 的上游必须是 A8 类型节点，否则拒绝执行（设计稿已有 `policy_decision` 表，未接执行）。
3. **提示词版本留痕**：`prompt_id/version/ab_group` 无处落地。建议扩展 `aiChat.config` 加 `promptMeta` 字段，并在 `agent_invocation` 落库时记录。
4. **KB 必须先建**：`kbSearch.config.kb` 引用的 `KB-QA-百问百答` / `KB-MED-耳病专业知识` 需在知识库模块先建表并灌入 SOP 第五/八章内容，否则 RAG 空检索会降级为"帮您问药师"。
