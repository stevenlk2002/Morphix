#!/usr/bin/env python3
"""
fix_ai_input_handles.py — 修正 SOP 编排图中 aiChat「用户问题」入边的 handle 名。

根因：
  编辑器 CustomNode 对普通节点渲染时，输入端口 handle id = inp.key，
  输出端口 handle id = out.varName（见 src/.../CustomNode.tsx:269/:301）。
  aiChat 的「用户问题」输入定义 key='question'、varName='userChatInput'，
  故真实输入端口 id 是 'question'。
  原图 n_user -> 各 aiChat 的边（e1-e9）targetHandle 错写成 'userChatInput'，
  导致 ReactFlow 找不到 handle（线画不出），且 useValidation 判定
  e.targetHandle === 'question' 为 False（校验报「用户问题」必填未连线）。

修正：将这 9 条边的 targetHandle 从 'userChatInput' 改为 'question'（与 UI 拖动连线产物一致）。
幂等：仅修正 targetHandle=='userChatInput' 且目标节点 nodeType=='aiChat' 的边。

用法：
  python3 fix_ai_input_handles.py            # 预览
  python3 fix_ai_input_handles.py --yes      # 执行写入
"""
import argparse
import shutil
import sqlite3
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent  # project/backend/scripts -> 仓库根(Morphix)
DB_PATH = ROOT / "database" / "morphix_mvp.db"
SRC_JSON = ROOT / "docs" / "hema-sop-morphix-workflow.json"
BOT_ID = "hema"
WRONG_HANDLE = "userChatInput"
RIGHT_HANDLE = "question"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="确认执行写入")
    ap.add_argument("--db", default=str(DB_PATH), help="DB 路径")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"❌ DB 不存在: {db}")
        return 1

    c = sqlite3.connect(str(db)); c.row_factory = sqlite3.Row
    row = c.execute(
        "SELECT data FROM orchestration_workflows WHERE bot_id=?", (BOT_ID,)
    ).fetchone()
    if not row:
        print(f"❌ 未找到 bot_id={BOT_ID} 的编排数据")
        c.close(); return 1

    graph = json.loads(row["data"])
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # 节点 id -> nodeType
    ntype = {n["id"]: n["data"].get("nodeType") for n in nodes}

    fixable = [
        e for e in edges
        if e.get("targetHandle") == WRONG_HANDLE
        and ntype.get(e.get("target")) == "aiChat"
    ]
    print(f"预览：bot={BOT_ID}  节点={len(nodes)} 边={len(edges)}")
    print(f"待修正边（targetHandle {WRONG_HANDLE} -> {RIGHT_HANDLE}）：{len(fixable)}")
    for e in fixable:
        print(f"  {e['id']}: {e['source']} -> {e['target']}  [{e.get('sourceHandle')}]->[{WRONG_HANDLE}]")

    if not args.yes:
        print("\n（预览模式）加 --yes 执行写入。")
        c.close(); return 0

    # 备份
    bak = db.with_suffix(f".bak-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy(db, bak)
    print(f"\n✅ 已备份: {bak.name}")

    for e in fixable:
        e["targetHandle"] = RIGHT_HANDLE

    graph["lastEdited"] = datetime.now().isoformat()
    c.execute(
        "UPDATE orchestration_workflows SET data=?, updated_at=? WHERE bot_id=?",
        (json.dumps(graph, ensure_ascii=False), graph["lastEdited"], BOT_ID),
    )
    c.commit()

    # 校验
    ok = sum(1 for e in edges if e.get("targetHandle") == RIGHT_HANDLE and ntype.get(e.get("target")) == "aiChat")
    print(f"✅ 写入完成：aiChat 入边中 targetHandle='question' 共 {ok} 条")

    # 同步源文件
    if SRC_JSON.exists():
        graph["botId"] = BOT_ID
        with open(SRC_JSON, "w", encoding="utf-8") as f:
            json.dump(graph, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"✅ 已同步源文件: {SRC_JSON.name}")

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
