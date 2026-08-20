from fastapi import APIRouter

from server.extensions import ExtensionManager

router = APIRouter()


@router.get("/api/extensions")
async def extensions():
    return ExtensionManager.instance().extensions
