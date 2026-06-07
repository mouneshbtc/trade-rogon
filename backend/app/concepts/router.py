from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from app.deps import ConceptRegistry, DBSession
from app.schemas.concept import ConceptDefinitionCreate, ConceptDefinitionOut, ConceptSummaryOut

router = APIRouter(prefix="/concepts", tags=["concepts"])


@router.get("", response_model=list[ConceptSummaryOut])
async def list_concepts(db: DBSession, registry: ConceptRegistry) -> list[ConceptSummaryOut]:
    """Every concept that has at least one authored definition, with its active version."""
    summaries = []
    for name in await registry.list_concept_names(db):
        versions = await registry.list_versions(db, name)
        active = next((v for v in versions if v.is_active), None)
        summaries.append(
            ConceptSummaryOut(
                concept_name=name,
                active_definition=ConceptDefinitionOut.model_validate(active) if active else None,
                version_count=len(versions),
            )
        )
    return summaries


@router.get("/{concept_name}/versions", response_model=list[ConceptDefinitionOut])
async def list_concept_versions(
    concept_name: str, db: DBSession, registry: ConceptRegistry
) -> list[ConceptDefinitionOut]:
    versions = await registry.list_versions(db, concept_name)
    if not versions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept has no definitions yet")
    return [ConceptDefinitionOut.model_validate(v) for v in versions]


@router.post(
    "/{concept_name}/versions",
    response_model=ConceptDefinitionOut,
    status_code=status.HTTP_201_CREATED,
)
async def propose_concept_version(
    concept_name: str,
    payload: ConceptDefinitionCreate,
    db: DBSession,
    registry: ConceptRegistry,
) -> ConceptDefinitionOut:
    """Record the structured outcome of a Developer Mode clarification cycle.

    The new version is inactive until explicitly activated — proposing a
    definition and trusting it in production are deliberately separate steps.
    """
    if payload.concept_name != concept_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path concept_name and payload concept_name must match",
        )
    definition = await registry.propose_version(
        db,
        concept_name=concept_name,
        rules=payload.rules,
        notes=payload.notes,
        created_by=payload.created_by,
    )
    return ConceptDefinitionOut.model_validate(definition)


@router.patch("/{concept_name}/activate/{version}", response_model=ConceptDefinitionOut)
async def activate_concept_version(
    concept_name: str, version: int, db: DBSession, registry: ConceptRegistry
) -> ConceptDefinitionOut:
    definition = await registry.activate_version(
        db, concept_name=concept_name, version=version, at=datetime.now(UTC)
    )
    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    return ConceptDefinitionOut.model_validate(definition)
