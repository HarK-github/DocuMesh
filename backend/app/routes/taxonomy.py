"""Taxonomy endpoint returning valid labels and relation types."""

from fastapi import APIRouter
from backend.app.schemas import TaxonomyResponse
from backend.app.taxonomy import TAXONOMY_LABELS, TAXONOMY_RELATION_TYPES

router = APIRouter(prefix="/taxonomy", tags=["Taxonomy"])


@router.get("", response_model=TaxonomyResponse)
def get_taxonomy() -> TaxonomyResponse:
    """Return all valid annotation labels and relation types from taxonomy configuration."""
    return TaxonomyResponse(labels=TAXONOMY_LABELS, relation_types=TAXONOMY_RELATION_TYPES)

