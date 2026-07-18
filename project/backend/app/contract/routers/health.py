from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/api/health")
def health():
    return {"service": "Morphix Control", "status": "ok"}
