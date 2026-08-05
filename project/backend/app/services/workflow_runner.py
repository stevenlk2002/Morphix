"""编排工作流真实执行服务。

把"编排测试"从前端 mock 提升为**真实后端执行**：
- kbSearch 节点 → 检索真实 knowledge_base（按 bot_id，带同义/词重叠扩展）
- aiChat 节点   → 调真实 LLM（primary 配置）；无可用密钥时回落到"基于知识库拼装"的实体回答
- msgOutput 节点 → 收集最终回复文本

返回 { finalReply, trace, usedRealLLM, kbHits }，供前端测试面板渲染。
"""
from __future__ import annotations

import json
import re
import time
from collections import deque
from typing import Any

from app.contract.services.agents import (
    _call_openai_compatible,
    resolve_llm_credentials,
)
from app.database import get_backend
from app.repositories import OrchestrationWorkflowRepository

# ── 同义词扩展：把口语化症状映射到知识库用词 ──
_SYNONYMS = {
    "耳朵嗡嗡响": "耳鸣",
    "嗡嗡响": "耳鸣",
    "耳朵响": "耳鸣",
    "耳内有声音": "耳鸣",
    "头晕": "眩晕",
    "肚子疼": "腹痛",
}

_FALLBACK_MODEL = "primary"


def _expand(text: str) -> str:
    out = text
    for k, v in _SYNONYMS.items():
        if k in out:
            out = out.replace(k, f"{k} {v} ")
    return out


def _tokenize(text: str) -> set[str]:
    text = re.sub(r"\s+", "", text or "")
    toks = set(text)  # 单字
    for i in range(len(text) - 1):
        toks.add(text[i : i + 2])  # 二元组
    return toks


def _retrieve_kb(bot_id: str, query: str, top_k: int = 6) -> list[dict]:
    """从 knowledge_base 检索与 query 相关的 SOP 知识条目。"""
    backend = get_backend()
    rows = backend.query(
        "SELECT id, kind, question, answer, tags FROM knowledge_base WHERE bot_id=?",
        (bot_id,),
    )
    if not rows:
        return []
    q_tokens = _tokenize(_expand(query))
    if not q_tokens:
        return []
    scored: list[tuple[int, dict]] = []
    for r in rows:
        doc = f"{r.get('question') or ''} {r.get('answer') or ''}"
        d_tokens = _tokenize(doc)
        overlap = len(q_tokens & d_tokens)
        if overlap > 0:
            scored.append((overlap, r))
    scored.sort(key=lambda x: -x[0])
    return [dict(r) for _, r in scored[:top_k]]


def _compose_from_kb(kb_hits: list[dict], query: str) -> str:
    """无可用 LLM 时，用检索到的知识库条目拼装实体回答。"""
    if not kb_hits:
        return (
            "（未检索到相关知识库内容，请先在「知识库」中补充 SOP 资料；"
            "或在「LLM 配置」中填入有效的 primary 模型密钥以生成智能回复。）"
        )
    parts = [f"针对您提到的「{query}」，结合我们的健康知识库："]
    for i, hit in enumerate(kb_hits[:4], 1):
        ans = (hit.get("answer") or "").strip()
        if ans:
            parts.append(f"{i}. {ans}")
    parts.append("（以上为知识库参考内容，具体用药/诊疗请遵医嘱。）")
    return "\n".join(parts)


def _ai_chat(node_config: dict, user_message: str, kb_hits: list[dict]) -> tuple[str, bool]:
    """执行 aiChat 节点：调真实 LLM；失败回落知识库拼装。返回 (reply, used_real_llm)。"""
    system_prompt = (node_config or {}).get("prompt") or "你是一个专业的健康私域客服顾问。"
    kb_block = ""
    if kb_hits:
        kb_block = "\n\n【参考知识库】\n" + "\n".join(
            f"- {h.get('question','')}: {h.get('answer','')}" for h in kb_hits[:4]
        )
    user_prompt = f"用户消息：{user_message}{kb_block}\n\n请基于以上信息给出专业、合规、简洁的回复。"

    creds = resolve_llm_credentials(_FALLBACK_MODEL)
    if creds and creds.get("enabled", True) and creds.get("api_key") and creds.get("api_key") != "••••••••":
        reply = _call_openai_compatible(creds, system_prompt, user_prompt)
        if reply:
            return reply, True
    # 回落：基于知识库的实体回答
    return _compose_from_kb(kb_hits, user_message), False


def run_workflow(bot_id: str, message: str) -> dict[str, Any]:
    """执行指定 bot 的编排工作流（真实后端执行），返回执行结果与逐节点 trace。"""
    backend = get_backend()
    row = OrchestrationWorkflowRepository(backend).load(bot_id)
    if not row:
        return {"error": "workflow_not_found", "finalReply": "", "trace": [], "usedRealLLM": False, "kbHits": 0}

    graph = row["data"] if isinstance(row, dict) else json.loads(row["data"])
    if isinstance(graph, str):
        graph = json.loads(graph)
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # 构建 DAG
    adj: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    indeg: dict[str, int] = {n["id"]: 0 for n in nodes}
    for e in edges:
        if e["source"] in adj and e["target"] in adj:
            adj[e["source"]].append(e["target"])
            indeg[e["target"]] += 1

    # 拓扑排序（Kahn）
    q = deque([nid for nid, d in indeg.items() if d == 0])
    ind = dict(indeg)
    order: list[str] = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in adj[u]:
            ind[v] -= 1
            if ind[v] == 0:
                q.append(v)

    node_map = {n["id"]: n for n in nodes}
    outputs: dict[str, dict] = {}
    trace: list[dict] = []
    kb_cache: list[dict] = []
    used_real_llm = False
    final_reply = ""

    for nid in order:
        node = node_map.get(nid)
        if not node:
            continue
        nt = node.get("data", {}).get("nodeType")
        cfg = node.get("data", {}).get("config", {}) or {}
        # 收集上游输入
        collected: dict[str, Any] = {}
        for e in edges:
            if e["target"] == nid:
                so = outputs.get(e["source"])
                if so and e.get("sourceHandle"):
                    collected[e.get("targetHandle") or ""] = so.get(e["sourceHandle"])
        collected["userChatInput"] = message

        started = time.time()
        status = "success"
        mock_note = None
        error = None
        out: dict[str, Any] = {}

        try:
            if nt == "userInput":
                out = {"userChatInput": message, "msgType": "text"}
            elif nt == "kbSearch":
                kb_hits = _retrieve_kb(bot_id, message)
                kb_cache = kb_hits
                out = {"knowledges": kb_hits, "query": message}
            elif nt == "aiChat":
                reply, real = _ai_chat(cfg, message, kb_cache)
                used_real_llm = used_real_llm or real
                out = {"aiReply": reply}
                # 越靠近输出端的 aiChat 回复越可能是最终答案
                if len(reply) > len(final_reply):
                    final_reply = reply
            elif nt == "multiJudge":
                cond = str(collected.get("cond", collected.get("question", "")))
                mode = cfg.get("mode", "文本匹配")
                res = False
                if mode == "文本匹配":
                    res = cfg.get("matchText", "") in cond
                out = {"result": res}
            elif nt == "msgOutput":
                # 收集上游传来的消息文本
                msg = (
                    collected.get("message")
                    or collected.get("draft_messages")
                    or collected.get("reply")
                    or collected.get("aiReply")
                    or final_reply
                )
                if isinstance(msg, str) and msg.strip():
                    final_reply = msg
                out = {"message": final_reply}
                mock_note = "消息输出节点（真实执行）：已收集最终回复"
            elif nt in ("setMorphixTag", "setCustomerAttr", "interruptBefore"):
                out = {}
                mock_note = "属性/标签/中断节点（真实执行已透传）"
            else:
                out = {**collected}
                mock_note = "未识别节点类型，已透传输入"
        except Exception as e:  # noqa: BLE001
            status = "error"
            error = str(e)
            out = {}

        outputs[nid] = out
        finished = time.time()
        trace.append({
            "nodeId": nid,
            "nodeName": node.get("data", {}).get("subflowName") or nt or nid,
            "nodeType": nt or "unknown",
            "status": status,
            "startedAt": _iso(started),
            "finishedAt": _iso(finished),
            "durationMs": int((finished - started) * 1000),
            "inputs": collected,
            "outputs": out,
            "mockNote": mock_note,
            "error": error,
        })

    if not final_reply and kb_cache:
        final_reply = _compose_from_kb(kb_cache, message)

    return {
        "finalReply": final_reply,
        "trace": trace,
        "usedRealLLM": used_real_llm,
        "kbHits": len(kb_cache),
    }


def _iso(t: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()
