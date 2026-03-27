from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key")


async def require_admin_key(api_key: str = Depends(api_key_header)) -> str:
    if api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
