from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Request

from app.routers.mixes import limiter
from app.schemas.contact import ContactRequest, ContactResponse
from app.services.contact_service import ContactService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contact", tags=["contact"])


async def get_contact_service() -> AsyncGenerator[ContactService]:
    """Factory for ContactService. Handles client lifecycle."""
    service = ContactService()
    try:
        yield service
    finally:
        await service.close()


@router.post("", response_model=ContactResponse)
@limiter.limit("3/hour")  # type: ignore[misc]
async def submit_contact(
    request: Request,  # required by slowapi for IP extraction
    body: ContactRequest,
    service: ContactService = Depends(get_contact_service),
) -> ContactResponse:
    """Receive a contact-form submission and forward it as an email."""
    if body.website:
        logger.info("Contact form honeypot triggered, dropping submission")
        return ContactResponse(sent=True)

    await service.send_contact_message(
        name=body.name,
        email=body.email,
        message=body.message,
    )
    return ContactResponse(sent=True)
