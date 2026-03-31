from uuid import UUID

from pydantic import BaseModel


class GenreResponse(BaseModel):
    id: UUID
    name: str
    slug: str

    class Config:
        from_attributes = True
