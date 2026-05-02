from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from app.routers.mixes import limiter
from app.schemas.contact import ContactRequest, ContactResponse
from app.services.contact_service import ContactService
from app.services.email_client import EmailClient, get_email_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contact", tags=["contact"])


def get_contact_service(
    email_client: EmailClient = Depends(get_email_client),
) -> ContactService:
    """Factory for ContactService. The EmailClient lifecycle is owned by `get_email_client`."""
    return ContactService(email_client=email_client)


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
