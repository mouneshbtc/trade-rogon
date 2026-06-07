import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ConceptDefinitionCreate(BaseModel):
    """Payload produced at the end of a Developer Mode clarification cycle."""

    concept_name: str = Field(..., min_length=1, max_length=100)
    rules: dict = Field(..., description="Structured, concept-specific rule payload")
    notes: str | None = None
    created_by: str | None = None


class ConceptDefinitionOut(BaseModel):
    id: uuid.UUID
    concept_name: str
    version: int
    rules: dict
    is_active: bool
    activated_at: datetime | None
    deactivated_at: datetime | None
    notes: str | None
    created_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConceptSummaryOut(BaseModel):
    """One row per concept — its currently active definition, if any."""

    concept_name: str
    active_definition: ConceptDefinitionOut | None
    version_count: int
