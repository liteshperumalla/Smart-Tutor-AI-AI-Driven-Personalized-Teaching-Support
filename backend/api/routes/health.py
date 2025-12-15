from fastapi import APIRouter


router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Health check", description="Verify API status")
async def health_check():
    return {"status": "ok"}
