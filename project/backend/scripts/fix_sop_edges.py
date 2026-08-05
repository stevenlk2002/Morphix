#!/usr/bin/env python3
"""
补全 SOP 编排图的缺失边连线。

根因分析（2026-08-05）：
  原图 docs/hema-sop-morphix-workflow.json 有 23 节点 / 27 边，
  但多条逻辑链路断裂——生成客户消息的 Agent 未接入合规审查链(n_a8→n_judge→n_msg)。

  缺失边清单：
    e28  n_a0(调度器)     → n_a8(合规)   : aiReply→question  （调度器可能输出路由消息）
    e29  n_a3(病历摘要)   → n_a8(合规)   : aiReply→question  （customer_confirm_text 需合规）
    e30  n_a6(沉默唤醒)   → n_a8(合规)   : aiReply→question  （draft_messages 需合规）
    e31  n_a7(成交交接)   → n_a8(合规)   : aiReply→question  （B1-B5 文案需合规）
    e32  n_a5(成交信号)   → n_a8(合规)   : aiReply→question  （coach_tip 可能触发消息）
    e33  n_a9(标签)       → n_a8(合规)   : aiReply→question  （标签回调可能附带消息）

用法：
  python scripts/fix_sop_edges.py          # preview（只打印不写入）
  python scripts/fix_sop_edges.py --yes    # 执行写入 DB + 更新源文件
"""
import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # scripts/ → backend/ → project/ → Morphix/
DB_PATH = REPO_ROOT / "database" / "morphix_mvp.db"
SOURCE_JSON = REPO_ROOT / "docs" / "hema-sop-morphix-workflow.json"
BOT_ID = "hema"

# ====== 缺失边定义 ======
MISSING_EDGES = [
    {
        "id": "e28",
        "source": "n_a0",
        "target": "n_a8",
        "sourceHandle": "aiReply",
        "targetHandle": "question",
        "reason": "A0调度器路由决策消息需经合规审查",
    },
    {
        "id": "e29",
        "source": "n_a3",
        "target": "n_a8",
        "sourceHandle": "aiReply",
        "targetHandle": "question",
        "reason": "A3病历摘要确认文本(customer_confirm_text)需经合规审查",
    },
    {
        "id": "e30",
        "source": "n_a6",
        "target": "n_a8",
        "sourceHandle": "aiReply",
        "targetHandle": "question",
        "reason": "A6沉默唤醒draft_messages需经合规审查后发送",
    },
    {
        "id": "e31",
        "source": "n_a7",
        "target": "n_a8",
        "sourceHandle": "aiReply",
        "targetHandle": "question",
        "reason": "A7成交交接B1-B5文案需经合规审查",
    },
    {
        "id": "e32",
        "source": "n_a5",
        "target": "n_a8",
        "sourceHandle": "aiReply",
        "targetHandle": "question",
        "reason": "A5成交信号coach_tip/suggested_action可能触发客户消息",
    },
    {
        "id": "e33",
        "source": "n_a9",
        "target": "n_a8",
        "sourceHandle": "aiReply",
        "targetHandle": "question",
        "reason": "A9标签回调可能附带客户触达消息",
    },
]


def load_graph(db_path: Path, bot_id: str) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT data FROM orchestration_workflows WHERE bot_id=?", (bot_id,)
    ).fetchone()
    if not row:
        print(f"[ERROR] bot_id={bot_id} 在 orchestration_workflows 中无记录")
        conn.close()
        SystemExit(1)
    data = json.loads(row["data"])
    conn.close()
    return data


def save_graph(db_path: Path, bot_id: str, data: dict):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """UPDATE orchestration_workflows
           SET data=?, updated_at=?
           WHERE bot_id=?""",
        (json.dumps(data, ensure_ascii=False), datetime.now(timezone.utc).isoformat(), bot_id),
    )
    conn.commit()
    conn.close()


def update_source_file(source_path: Path, data: dict):
    with open(source_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    parser = argparse.ArgumentParser(description="补全 SOP 编排图缺失边")
    parser.add_argument("--yes", action="store_true", help="实际执行（不加则仅预览）")
    args = parser.parse_args()

    # ---- 加载当前数据 ----
    graph = load_graph(DB_PATH, BOT_ID)
    existing_ids = {e["id"] for e in graph.get("edges", [])}

    # ---- 检查哪些边需要加 ----
    to_add = [e for e in MISSING_EDGES if e["id"] not in existing_ids]
    already_exists = [e for e in MISSING_EDGES if e["id"] in existing_ids]

    print(f"=== SOP 编排图补边预览 ===")
    print(f"  当前节点: {len(graph.get('nodes',[]))}")
    print(f"  当前边数: {len(graph.get('edges',[]))}")
    print(f"  待新增边: {len(to_add)}")
    print(f"  已存在边: {len(already_exists)}")
    print()

    if already_exists:
        print("[INFO] 以下边已存在，跳过：")
        for e in already_exists:
            print(f"  {e['id']}: {e['source']}→{e['target']}  ({e['reason']})")
        print()

    if not to_add:
        print("✅ 所有需要的边都已存在，无需修改。")
        return

    print("待新增边：")
    for e in to_add:
        clean = {k: v for k, v in e.items() if k != "reason"}
        print(f"  {e['id']}: {e['source']}→{e['target']}  "
              f"({e['sourceHandle']}→{e['targetHandle']})  // {e['reason']}")

    if not args.yes:
        print("\n[预览模式] 加 --yes 执行写入。")
        return

    # ---- 备份 DB ----
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = DB_PATH.with_suffix(f".db.bak-{ts}")
    shutil.copy2(DB_PATH, backup)
    print(f"\n[备份] DB → {backup.name}")

    # ---- 备份源文件 ----
    src_backup = SOURCE_JSON.with_suffix(f".json.bak-{ts}")
    shutil.copy2(SOURCE_JSON, src_backup)
    print(f"[备份] 源文件 → {src_backup.name}")

    # ---- 写入新边到 graph ----
    new_edge_dicts = [
        {k: v for k, v in e.items() if k != "reason"} for e in to_add
    ]
    graph["edges"].extend(new_edge_dicts)

    # ---- 写入 DB ----
    save_graph(DB_PATH, BOT_ID, graph)
    print(f"[DB] 已写入 {len(new_edge_dicts)} 条新边，总计 {len(graph['edges'])} 条")

    # ---- 更新源文件（同步修正 botId）----
    graph["botId"] = BOT_ID
    graph["lastEdited"] = datetime.now().isoformat()
    update_source_file(SOURCE_JSON, graph)
    print(f"[源文件] 已同步更新 {SOURCE_JSON.name}")

    # ---- 校验 ----
    verify = load_graph(DB_PATH, BOT_ID)
    final_edges = verify.get("edges", [])
    final_ids = {e["id"] for e in final_edges}
    print(f"\n[校验] 最终边数: {len(final_edges)}")
    missing_check = [e for e in MISSING_EDGES if e["id"] not in final_ids]
    if missing_check:
        print("[ERROR] 以下边仍缺失！")
        for e in missing_check:
            print(f"  {e['id']}")
    else:
        print("✅ 所有必要边均已就位")

    # 打印最终连接度
    from collections import defaultdict
    indeg, outdeg = defaultdict(int), defaultdict(int)
    for e in final_edges:
        outdeg[e["source"]] += 1
        indeg[e["target"]] += 1
    print("\n--- 补完后节点连接度 ---")
    print(f"  {'node':18s}  {'in':>3s}  {'out':>3s}  type")
    for n in verify["nodes"]:
        nid = n["id"]
        nt = n["data"].get("nodeType", "?")
        marker = ""
        if indeg[nid] == 0 and nt != "userInput":
            marker = " ⚠️ 无入边"
        if outdeg[nid] == 0 and nt not in ("msgOutput", "setMorphixTag", "setCustomerAttr"):
            marker += " ⚠️ 无出边"
        print(f"  {nid:18s}  {indeg[nid]:3d}  {outdeg[nid]:3d}  {nt}{marker}")


if __name__ == "__main__":
    main()
