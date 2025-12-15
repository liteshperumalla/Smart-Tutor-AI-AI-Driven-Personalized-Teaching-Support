from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path

from backend.api.dependencies import get_session_with_optional_query_token


router = APIRouter(prefix="/files", tags=["files"])


def _resolve_path(raw_path: str) -> Path:
    resolved = Path(raw_path).expanduser().resolve()
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return resolved


@router.get("/view")
def view_file(
    path: str = Query(...),
    session=Depends(get_session_with_optional_query_token),
):
    file_path = _resolve_path(path)
    return FileResponse(file_path)


@router.get("/download")
def download_file(
    path: str = Query(...),
    session=Depends(get_session_with_optional_query_token),
):
    file_path = _resolve_path(path)
    return FileResponse(
        file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )
