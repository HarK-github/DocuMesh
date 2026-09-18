"""Taxonomy endpoint returning valid labels and relation types."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.db import get_db
from backend.app.models import Label, RelationType
from backend.app.schemas import TaxonomyResponse

router = APIRouter(prefix="/taxonomy", tags=["Taxonomy"])


@router.get("", response_model=TaxonomyResponse)
def get_taxonomy(db: Session = Depends(get_db)) -> TaxonomyResponse:
    """Return all valid annotation labels and relation types seeded in the DB."""
    labels = [l.name for l in db.query(Label).order_by(Label.name).all()]
    rel_types = [r.name for r in db.query(RelationType).order_by(RelationType.name).all()]
    return TaxonomyResponse(labels=labels, relation_types=rel_types)
