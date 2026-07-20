"""训练对话路由（训练记录 + 训练消息）。

路径：
- GET    /api/bots/{bot_id}/training/records
- POST   /api/bots/{bot_id}/training/records            {title?}
- DELETE /api/training/records/{record_id}
- GET    /api/training/records/{record_id}/messages
- POST   /api/training/records/{record_id}/messages      {role, content, recordRef?}
- PUT    /api/training/messages/{message_id}/feedback    {feedback: 'like'|'dislike'|null}

训练「发送」由前端 1s 模拟 AI 回复后走同一消息接口写入，后端不接 LLM。
feedback 更新由服务端重算该记录的 good/bad/total（仅统计 role='ai'）。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..database import get_backend
from ..pagination import make_id
from ..repositories import AuditRepository, TrainingRepository
from ..schemas import TrainingFeedbackUpdate, TrainingMessageCreate, TrainingRecordCreate

router = APIRouter(tags=["training"])


@router.get("/bots/{bot_id}/training/records")
def list_training_records(bot_id: str):
    """列出某 bot 的训练记录（含 good/bad/total 统计）。"""
    return TrainingRepository(get_backend()).list_records(bot_id)


@router.post("/bots/{bot_id}/training/records")
def create_training_record(bot_id: str, payload: TrainingRecordCreate):
    """新建训练记录；title 为空时后端用「训练记录 {id后缀}」兜底。"""
    backend = get_backend()
    record_id = make_id("rec")
    title = payload.title or f"训练记录 {record_id.split('-')[-1]}"
    with backend.transaction() as tx:
        record = TrainingRepository(tx).create_record(record_id, bot_id, title)
        AuditRepository(tx).record("create_training_record", record_id, title)
    return record


@router.delete("/training/records/{record_id}")
def delete_training_record(record_id: str):
    """级联删除训练记录及其全部消息。"""
    backend = get_backend()
    with backend.transaction() as tx:
        repo = TrainingRepository(tx)
        existing = repo.get_record(record_id)
        if not existing:
            raise HTTPException(status_code=404, detail="训练记录不存在")
        repo.delete_record(record_id)
        AuditRepository(tx).record("delete_training_record", record_id, existing["title"])
    return {"id": record_id, "message": "删除成功"}


@router.get("/training/records/{record_id}/messages")
def list_training_messages(record_id: str):
    """列出某训练记录的消息流（按 msg_order ASC）。"""
    return TrainingRepository(get_backend()).list_messages(record_id)


@router.post("/training/records/{record_id}/messages")
def create_training_message(record_id: str, payload: TrainingMessageCreate):
    """写入一条训练消息；msg_order 自动取当前最大 + 1。"""
    backend = get_backend()
    message_id = make_id("msg")
    with backend.transaction() as tx:
        repo = TrainingRepository(tx)
        record = repo.get_record(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="训练记录不存在")
        message = repo.create_message(
            message_id,
            record_id,
            record["botId"],
            payload.role,
            payload.content,
            payload.recordRef or "",
        )
        AuditRepository(tx).record("create_training_message", message_id, payload.role)
    return message


@router.put("/training/messages/{message_id}/feedback")
def update_training_feedback(message_id: str, payload: TrainingFeedbackUpdate):
    """更新消息 feedback，服务端重算该记录 good/bad/total 并返回最新统计。"""
    backend = get_backend()
    with backend.transaction() as tx:
        repo = TrainingRepository(tx)
        message = backend.query_one(
            "SELECT id FROM training_messages WHERE id = ?", (message_id,)
        )
        if not message:
            raise HTTPException(status_code=404, detail="训练消息不存在")
        record = repo.update_feedback(message_id, payload.feedback)
    return {
        "id": message_id,
        "feedback": payload.feedback,
        "record": record,
    }
