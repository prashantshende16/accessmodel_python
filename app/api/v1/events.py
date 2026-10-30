from typing import Optional
from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...schemas.event import EventIngestSchema, EventResponse
from ...services.ingestion import ingest_error_event

router = APIRouter(prefix="/events", tags=["Event Ingestion"])

@router.post("", response_model=EventResponse, status_code=202)
def receive_event(
    payload: EventIngestSchema,
    x_errorwatch_key: Optional[str] = Header(None, alias="X-ErrorWatch-Key"),
    db: Session = Depends(get_db)
):
    """
    Public ingestion endpoint for ErrorWatch SDKs and integrations.
    Authenticates via X-ErrorWatch-Key header or client_key in JSON body.
    """
    event = ingest_error_event(db, payload, key_from_header=x_errorwatch_key)
    return {
        "event_id": event.id,
        "issue_id": event.issue_id,
        "status": "received"
    }

