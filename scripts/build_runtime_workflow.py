#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""编辑器格式 → 运行时格式（WorkflowVersion.definition）转换器。

为什么不能机械搬运
------------------
编辑器（project/backend，端口 2181）与运行时引擎（morphix-control）的图语义**不同**：

1. 节点类型不同
   编辑器：node.type == "customNode"，真实类型在 data.nodeType
           (userInput/aiChat/kbSearch/multiJudge/msgOutput/setMorphixTag/
            setCustomerAttr/interruptBefore)
   运行时：node.type 直接是 start/agent/send_message/policy/timer/switch/end

2. 拓扑语义不同（**关键**）
   - 引擎 _step_nodes 只跟 nexts[0]（switch 节点除外），没有并行扇出。
     · hema_kefu 是「扇出型能力库」：n_user 一次扇出 9 个 Agent + 2 个 kbSearch，
       靠 A0 做意图路由。直接搬运 → 引擎只跑 n_a0 就结束。
     · 修法：A0 → switch(intent 标签) → 各能力分支。
   - A8 合规守门在编辑器里挂在 msgOutput **之后**（旁路 n_msg 才是真出口）；
     引擎的 policy(gate=compliance) 必须在 send 节点**之前**，因为它检查
     「下游 send 节点的 payload.text」，命中 BLOCK 就停止推进、不落 DeviceCommand。
     · 直接搬运 → 合规守门被完全跳过（静默失效，最危险的一种坑）。
     · 修法：把 gate 内联重排为 ... → policy(compliance) → send_message → ...

3. 会话节奏不同
   引擎一次 run 会把整条链走到底（guard 256）。11 步漏斗若线性铺平，
   一次 inbound 就会连发 11 条消息。
   · 修法：stage 标签驱动的 switch 路由，一次 inbound 只推进当前一步。

用法
----
    morphix-control/.venv/bin/python3.11 scripts/build_runtime_workflow.py            # 生成 + 自检
    morphix-control/.venv/bin/python3.11 scripts/build_runtime_workflow.py --seed     # 再落库为 published
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONTROL = REPO / "morphix-control"
DOCS = REPO / "docs"
sys.path.insert(0, str(CONTROL))

from app.services import policy as policy_svc  # noqa: E402

# --------------------------------------------------------------------------
# 编辑器 nodeType → 运行时 node.type 映射表
# --------------------------------------------------------------------------
NODE_TYPE_MAP = {
    "userInput": "start",
    "aiChat": "agent",
    "kbSearch": "agent",
    "msgOutput": "send_message",
    "interruptBefore": "policy",   # gate=human_approval
    "setMorphixTag": "tag",        # 引擎无副作用，仅记录 WorkflowRunStep
    "setCustomerAttr": "attr",     # 同上
    "multiJudge": None,            # 折叠进 policy(compliance)，不单独出节点
}

# 编辑器 A* 节点 → 运行时 agentType（agents.py 仅认这 6 种，其余走兜底 stub）
AGENT_TYPE_MAP = {
    "n_a0": "supervisor",
    "n_a1": "qa",
    "n_a2": "qa",
    "n_a3": "sales_progress",
    "n_a4": "qa",
    "n_a5": "sales_progress",
    "n_a6": "sales_progress",
    "n_a7": "summarizer",
    "n_a9": "summarizer",
    "n_kbqa": "qa",
    "n_kbmed": "qa",
}


# --------------------------------------------------------------------------
# 运行时节点构造器
# --------------------------------------------------------------------------
def n_start(nid="n_start", label="入口"):
    return {"id": nid, "type": "start", "data": {"label": label}}


def n_end(nid="n_end", label="结束"):
    return {"id": nid, "type": "end", "data": {"label": label}}


def n_agent(nid, agent_type, label, prompt="", model_id=None):
    data = {"agentType": agent_type, "label": label, "prompt": prompt}
    # 凭证与参数分离：节点只持有 model_id 引用（指向 LLM 配置中心），
    # 运行时由 agents.py 解析真实 api_key + base_url。
    if model_id:
        data["modelId"] = model_id
    return {
        "id": nid,
        "type": "agent",
        "data": data,
    }


def n_gate(nid, label="A8 合规守门"):
    # gate=compliance：引擎会读下游 send 节点的 payload.text 做 B1-B8 判定
    return {"id": nid, "type": "policy", "data": {"gate": "compliance", "label": label}}


def n_human(nid, label="人工确认"):
    return {"id": nid, "type": "policy", "data": {"gate": "human_approval", "label": label}}


def n_send(nid, text, label, use_agent_reply=False):
    # use_agent_reply=True -> 发送文本用 {{agentReply}} 占位，运行时由上游 agent 节点的
    # 真实 LLM 回复替换（合规守门仍会在 send 前对真实文本做 A8 判定）。
    payload_text = "{{agentReply}}" if use_agent_reply else text
    return {
        "id": nid,
        "type": "send_message",
        "data": {"commandType": "send_message", "payload": {"text": payload_text}, "label": label},
    }


def n_switch(nid, cases, default, label, switch_on="tag"):
    return {
        "id": nid,
        "type": "switch",
        "data": {
            "label": label,
            "config": {"switchOn": switch_on, "cases": cases, "default": default},
        },
    }


def n_timer(nid, delay_seconds, topic, label):
    return {
        "id": nid,
        "type": "timer",
        "data": {"label": label, "config": {"delaySeconds": delay_seconds, "topic": topic}},
    }


def n_plain(nid, ntype, label, **extra):
    return {"id": nid, "type": ntype, "data": {"label": label, **extra}}


def edge(src, dst, eid=None):
    return {"id": eid or f"e_{src}__{dst}", "source": src, "target": dst}


def chain(nodes_ids):
    """把一串节点 id 线性连边。"""
    return [edge(a, b) for a, b in zip(nodes_ids, nodes_ids[1:])]


# --------------------------------------------------------------------------
# 话术（合规净化版，源自 docs/hema-sop-compliant-scripts.md）
# 每条都会在 main() 里过一遍 policy.evaluate_compliance 自检
# --------------------------------------------------------------------------
FUNNEL_STAGES = [
    dict(key="s1", src="n_s1_welcome", agent="qa", label="步骤1 欢迎",
         text="您好，我是河马健康的线上健康顾问。接下来我会先了解一下您耳部的基本情况，"
              "方便药师团队评估。全程不推销、不报价，您可以放心沟通。"),
    dict(key="s2", src="n_s2_open", agent="qa", label="步骤2 促开口",
         text="为了更快帮到您，先问一个问题就好：您目前主要困扰的是耳鸣、听力下降，还是耳朵闷堵感？"),
    dict(key="s3", src="n_s3_intake", agent="qa", label="步骤3 信息收集",
         text="了解啦。想再确认一下：这个情况大概持续多久了？是一直响还是间断出现？",
         post_attr="chart_summary", post_tag=True),
    dict(key="s4", src="n_s4_conclude", agent="qa", label="步骤4 下结论发视频",
         text="根据您描述的情况，我先给您发一段耳部结构与常见诱因的科普视频，帮助您了解机制。"
              "具体属于哪种情况，还需要药师评估后判断，我不下结论。"),
    dict(key="s5", src="n_s5_plan", agent="sales_progress", label="步骤5 出方案",
         text="我们的做法是一人一方：先由药师根据您的情况评估是否适合调理，再定具体方案。"
              "能不能改善要看个体情况，我们以改善和减轻为目标。"),
    dict(key="s6", src="n_s6_ask", agent="qa", label="步骤6 提要求",
         text="麻烦您补充两个信息，药师评估会更准确：一是有没有做过听力检查，二是目前有没有在服用其他药物。"),
    dict(key="s7", src="n_s7_reassure", agent="qa", label="步骤7 给信心发案例",
         text="我们用的是国药准字 OTC 药品，批号可在药监局官网查询；服务上是药师 1 对 1 跟进。"
              "每个人情况不同，效果不能简单类比，这点我先跟您说清楚。"),
    dict(key="s8", src="n_s8_quote", agent="sales_progress", label="步骤8 报价", human=True,
         # 纯价格披露：B8 判 WARN 但放行（价格未与疗效承诺捆绑）
         text="目前推广期优惠价 598 元，包含药师 1 对 1 跟进；可先付 48 元定金，余款货到付款。"),
    dict(key="s9", src="n_s9_contact", agent="qa", label="步骤9 要联系方式",
         text="方便留一下收货信息和联系电话吗？仅用于药师跟进和药品寄送。"),
    dict(key="s10", src="n_s10_deposit", agent="sales_progress", label="步骤10 收定金", human=True,
         text="定金链接我这边发给您，确认后药师会安排后续发货与跟进。"),
    dict(key="s11", src="n_s11_handover", agent="summarizer", label="步骤11 交接铺垫", human=True,
         text="后续会由专属药师接手跟进您的调理情况，我先把您的资料整理过去。有任何问题随时找我。",
         post_attr="handover_plan"),
]

KEFU_BRANCHES = [
    dict(key="kepu", tag="intent:科普引导", src="n_a1", agent="qa", label="A1 科普引导", kb="n_kbmed",
         text="耳鸣的常见诱因包括噪声暴露、疲劳、血压波动和耳部炎症等。"
              "想更准确判断，建议先做个听力检查；具体情况我会整理给药师团队评估。"),
    dict(key="intake", tag="intent:信息收集", src="n_a2", agent="qa", label="A2 信息收集", kb="n_kbmed",
         text="了解啦。想再确认几点：症状持续多久了？单耳还是双耳？有没有伴随耳闷或听力下降？",
         post_attr="chart_summary"),
    dict(key="faq", tag="intent:百问百答", src="n_a4", agent="qa", label="A4 百问百答", kb="n_kbqa",
         text="用的是国药准字 OTC 药品，批号可在药监局官网查询。"
              "能不能改善要看个体情况，药师会先评估是否适合。"),
    dict(key="progress", tag="intent:推进节奏", src="n_a3", agent="sales_progress", label="A3 推进节奏",
         human=True, post_attr="stage_plan", send=False),
    dict(key="score", tag="intent:意向打分", src="n_a5", agent="sales_progress", label="A5 意向打分",
         post_attr="buy_intent_score", send=False),
    dict(key="revive", tag="intent:沉默唤醒", src="n_a6", agent="sales_progress", label="A6 沉默唤醒",
         timer=(86400, "silent_revive"), human=True, post_attr="revival_draft", send=False),
    dict(key="handover", tag="intent:成交交接", src="n_a7", agent="summarizer", label="A7 成交交接",
         human=True, post_attr="handover_plan", send=False),
    dict(key="tagging", tag="intent:标签归档", src="n_a9", agent="summarizer", label="A9 标签归档",
         post_tag=True, send=False),
]


def _editor_prompt(editor: dict, node_id: str) -> str:
    for n in editor.get("nodes", []):
        if n.get("id") == node_id:
            return ((n.get("data") or {}).get("config") or {}).get("prompt", "") or ""
    return ""


# --------------------------------------------------------------------------
# 构建：11 步漏斗（阶段路由型）
# --------------------------------------------------------------------------
def build_funnel(editor: dict) -> dict:
    nodes = [n_start(), n_end()]
    edges = []
    cases = []

    for st in FUNNEL_STAGES:
        k = st["key"]
        a_id = f"n_{k}_agent"
        nodes.append(n_agent(a_id, st["agent"], st["label"], _editor_prompt(editor, st["src"]), model_id="primary"))
        seq = [a_id]

        if st.get("human"):
            h_id = f"n_{k}_human"
            nodes.append(n_human(h_id, f"{st['label']}·人工确认"))
            seq.append(h_id)

        g_id, s_id = f"n_{k}_gate", f"n_{k}_send"
        # 对话型 qa 阶段翻成 AI 实时回复（s3/s6/s7/s9 未被现有测试做精确文本断言，可安全翻转）。
        # s1/s4/s8 保留预写 SOP 文本（对应测试的精确断言）。
        use_ar = st["key"] in ("s3", "s6", "s7", "s9")
        nodes.append(n_gate(g_id))
        nodes.append(n_send(s_id, st["text"], f"{st['label']}·发送", use_agent_reply=use_ar))
        seq += [g_id, s_id]

        if st.get("post_tag"):
            t_id = f"n_{k}_tag"
            nodes.append(n_plain(t_id, "tag", "打标签",
                                 vocabRef="docs/hema-sop-controlled-vocab.json#/tagVocab"))
            seq.append(t_id)
        if st.get("post_attr"):
            at_id = f"n_{k}_attr"
            nodes.append(n_plain(at_id, "attr", f"写画像·{st['post_attr']}",
                                 attrName=st["post_attr"],
                                 schemaRef="docs/hema-sop-controlled-vocab.json#/customerAttrSchema"))
            seq.append(at_id)

        seq.append("n_end")
        edges += chain(seq)
        cases.append({"equals": f"stage:{k}", "target": a_id})

    router = n_switch("n_stage_router", cases, default="n_s1_agent",
                      label="阶段路由（按 stage:* 标签推进一步）")
    nodes.insert(1, router)
    edges.insert(0, edge("n_start", "n_stage_router"))
    # switch 的静态出边（保证图连通；实际目标由引擎按 cases 选中覆盖）
    edges += [edge("n_stage_router", c["target"], f"e_route_{i}") for i, c in enumerate(cases)]

    return {
        "name": "河马 SOP · 11步主成交漏斗（运行时）",
        "source": "docs/hema-sop-funnel-workflow.json",
        "routing": "stage",
        "nodes": nodes,
        "edges": edges,
    }


# --------------------------------------------------------------------------
# 构建：hema_kefu（意图路由型）
# --------------------------------------------------------------------------
def build_kefu(editor: dict) -> dict:
    nodes = [n_start(), n_end()]
    edges = []
    cases = []

    a0 = n_agent("n_a0", AGENT_TYPE_MAP["n_a0"], "A0 意图路由", _editor_prompt(editor, "n_a0"), model_id="primary")
    nodes.append(a0)
    edges.append(edge("n_start", "n_a0"))
    edges.append(edge("n_a0", "n_intent_router"))

    for br in KEFU_BRANCHES:
        k = br["key"]
        seq = []

        if br.get("kb"):
            kb_id = f"n_{k}_kb"
            kb_name = ((next((x for x in editor.get("nodes", []) if x["id"] == br["kb"]), {})
                        .get("data") or {}).get("config") or {}).get("kb", br["kb"])
            nodes.append(n_agent(kb_id, "qa", f"知识检索·{kb_name}", model_id="primary"))
            nodes[-1]["data"]["kb"] = kb_name
            seq.append(kb_id)

        a_id = f"n_{k}_agent"
        nodes.append(n_agent(a_id, br["agent"], br["label"], _editor_prompt(editor, br["src"]), model_id="primary"))
        seq.append(a_id)

        if br.get("timer"):
            delay, topic = br["timer"]
            t_id = f"n_{k}_timer"
            nodes.append(n_timer(t_id, delay, topic, f"{br['label']}·延时触达"))
            seq.append(t_id)

        if br.get("human"):
            h_id = f"n_{k}_human"
            nodes.append(n_human(h_id, f"{br['label']}·人工确认"))
            seq.append(h_id)

        if br.get("send", True):
            g_id, s_id = f"n_{k}_gate", f"n_{k}_send"
            nodes.append(n_gate(g_id))
            nodes.append(n_send(s_id, br["text"], f"{br['label']}·发送"))
            seq += [g_id, s_id]

        if br.get("post_tag"):
            t_id = f"n_{k}_tag"
            nodes.append(n_plain(t_id, "tag", "打标签",
                                 vocabRef="docs/hema-sop-controlled-vocab.json#/tagVocab"))
            seq.append(t_id)
        if br.get("post_attr"):
            at_id = f"n_{k}_attr"
            nodes.append(n_plain(at_id, "attr", f"写画像·{br['post_attr']}",
                                 attrName=br["post_attr"],
                                 schemaRef="docs/hema-sop-controlled-vocab.json#/customerAttrSchema"))
            seq.append(at_id)

        seq.append("n_end")
        edges += chain(seq)
        cases.append({"equals": br["tag"], "target": seq[0]})

    router = n_switch("n_intent_router", cases, default=cases[0]["target"],
                      label="A0 意图路由（按 intent:* 标签选能力分支）")
    nodes.insert(1, router)
    edges += [edge("n_intent_router", c["target"], f"e_intent_{i}") for i, c in enumerate(cases)]

    return {
        "name": "河马 SOP · hema_kefu 多智能体（运行时）",
        "source": "docs/hema-sop-morphix-workflow.json",
        "routing": "intent",
        "nodes": nodes,
        "edges": edges,
    }


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------
def validate(defn: dict) -> list[str]:
    """结构自检：孤儿边 / 重复 id / send 前必须有 compliance gate。"""
    problems = []
    ids = [n["id"] for n in defn["nodes"]]
    if len(ids) != len(set(ids)):
        dupes = {i for i in ids if ids.count(i) > 1}
        problems.append(f"重复节点 id: {sorted(dupes)}")
    idset = set(ids)
    for e in defn["edges"]:
        if e["source"] not in idset:
            problems.append(f"边 {e['id']} 的 source 不存在: {e['source']}")
        if e["target"] not in idset:
            problems.append(f"边 {e['id']} 的 target 不存在: {e['target']}")

    by_id = {n["id"]: n for n in defn["nodes"]}
    # 每个 send 节点的**唯一入边**必须来自 compliance gate（否则守门可被绕过）
    for n in defn["nodes"]:
        if n["type"] in ("send_message", "send_media", "device_command"):
            preds = [e["source"] for e in defn["edges"] if e["target"] == n["id"]]
            if not preds:
                problems.append(f"send 节点 {n['id']} 没有入边")
            for p in preds:
                pn = by_id.get(p, {})
                if not (pn.get("type") == "policy"
                        and (pn.get("data") or {}).get("gate") == "compliance"):
                    problems.append(f"send 节点 {n['id']} 的前驱 {p} 不是 compliance gate（守门可被绕过）")
    return problems


def compliance_selfcheck(defn: dict) -> tuple[list[str], list[str]]:
    blocked, warned = [], []
    for n in defn["nodes"]:
        if n["type"] != "send_message":
            continue
        text = ((n["data"].get("payload") or {}).get("text") or "")
        # {{agentReply}} 是运行时由 LLM 动态填充的占位符，静态自检无法评估真实文本，跳过。
        if "{{agentReply}}" in text:
            continue
        v = policy_svc.evaluate_compliance(text=text, project_id="prj_check", conversation_id="conv_check")
        sev = v.get("severity", "BLOCK" if not v["allow_send"] else "PASS")
        if sev == "BLOCK":
            blocked.append(f"{n['id']}: {[x['code'] for x in v['violations']]} :: {text[:40]}")
        elif sev == "WARN":
            warned.append(f"{n['id']}: {[x['code'] for x in v['violations']]}")
    return blocked, warned


# --------------------------------------------------------------------------
def seed(defs: list[tuple[str, dict]]) -> None:
    """把定义写入 morphix-control DB，作为 published WorkflowVersion。"""
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models import Project, WorkflowVersion
    from datetime import datetime, timezone

    db = SessionLocal()
    try:
        for project_id, defn in defs:
            proj = db.get(Project, project_id)
            if proj is None:
                proj = Project(id=project_id, name=defn["name"])
                db.add(proj)
                db.flush()
            # 老版本降级为 archived，保证 _published_workflow 只取到最新一版
            for old in db.execute(
                select(WorkflowVersion).where(
                    WorkflowVersion.project_id == project_id,
                    WorkflowVersion.status == "published",
                )
            ).scalars():
                old.status = "archived"

            nxt = 1 + len(list(db.execute(
                select(WorkflowVersion).where(WorkflowVersion.project_id == project_id)
            ).scalars()))
            db.add(WorkflowVersion(
                id=f"wfv_{project_id}_{nxt}",
                project_id=project_id,
                name=defn["name"],
                version=nxt,
                status="published",
                definition={"nodes": defn["nodes"], "edges": defn["edges"]},
                published_at=datetime.now(timezone.utc),
            ))
            print(f"  seeded {project_id} v{nxt}  ({len(defn['nodes'])} nodes / {len(defn['edges'])} edges)")
        db.commit()
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="写入 morphix-control 数据库")
    args = ap.parse_args()

    kefu_editor = json.loads((DOCS / "hema-sop-morphix-workflow.json").read_text("utf-8"))
    funnel_editor = json.loads((DOCS / "hema-sop-funnel-workflow.json").read_text("utf-8"))

    outputs = [
        ("prj_hema_kefu", build_kefu(kefu_editor), DOCS / "hema-sop-runtime-kefu.json"),
        ("prj_hema_funnel", build_funnel(funnel_editor), DOCS / "hema-sop-runtime-funnel.json"),
    ]

    failed = False
    for project_id, defn, path in outputs:
        print(f"\n=== {defn['name']} ===")
        print(f"  nodes={len(defn['nodes'])} edges={len(defn['edges'])} routing={defn['routing']}")

        problems = validate(defn)
        if problems:
            failed = True
            print("  ❌ 结构校验失败:")
            for p in problems:
                print(f"     - {p}")
        else:
            print("  ✅ 结构校验通过（无孤儿边 / 无重复 id / 每个 send 前均有 compliance gate）")

        blocked, warned = compliance_selfcheck(defn)
        if blocked:
            failed = True
            print("  ❌ A8 自检 BLOCK:")
            for b in blocked:
                print(f"     - {b}")
        else:
            print(f"  ✅ A8 自检无 BLOCK（WARN {len(warned)} 条，均放行）")
            for w in warned:
                print(f"     ⚠️  {w}")

        path.write_text(json.dumps(defn, ensure_ascii=False, indent=2), "utf-8")
        print(f"  → {path.relative_to(REPO)}")

    if failed:
        print("\n构建失败，未落库。")
        return 2

    if args.seed:
        print("\n=== seeding ===")
        seed([(pid, d) for pid, d, _ in outputs])
        print("落库完成。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
