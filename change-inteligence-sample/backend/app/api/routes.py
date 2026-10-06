from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.domain.models import (ChangeType, DesignReviewIn, DesignReviewOut, DirectAccessOut, GovernanceSummary, GraphOut,
                               ImpactOut, ObjectDetail, ObjectRef, ResolveIn, ResolveOut, UnknownDetail, UnknownSummary)
from app.graph.snapshot import load_snapshot
from app.services import design_review, drift, governance, impact, llm, objects, unknowns
from app.services.ontology import load_ontology, rules

router = APIRouter(prefix="/api")


@router.get("/ontology")
def get_ontology() -> dict:
    return load_ontology()


@router.get("/objects", response_model=list[ObjectRef])
def list_objects(type: list[str] | None = Query(default=None), q: str | None = None):
    return objects.list_objects(load_snapshot(), types=type, q=q)


@router.get("/objects/{object_id:path}/graph", response_model=GraphOut)
def object_graph(object_id: str, depth: int = 2, include_resolved: bool = False):
    result = objects.neighbourhood(object_id, depth=depth, include_resolved=include_resolved)
    if result is None:
        raise HTTPException(status_code=404, detail="object not found")
    return result


@router.get("/objects/{object_id:path}", response_model=ObjectDetail)
def object_detail(object_id: str):
    result = objects.get_object(load_snapshot(), object_id)
    if result is None:
        raise HTTPException(status_code=404, detail="object not found")
    return result


@router.get("/impact", response_model=ImpactOut)
def impact_analysis(object_id: str, change_type: ChangeType = "schema_change"):
    result = impact.analyze(load_snapshot(), object_id, change_type, rules().get("impact"))
    if result is None:
        raise HTTPException(status_code=404, detail="object not found")
    return result


@router.get("/unknowns", response_model=list[UnknownSummary])
def list_unknowns(status: str = "open"):
    return unknowns.list_unknowns(load_snapshot(), status=status)


@router.get("/unknowns/{unknown_id:path}/candidates", response_model=list[ObjectRef])
def unknown_candidates(unknown_id: str):
    detail = unknowns.get_unknown(load_snapshot(), unknown_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="unknown not found")
    return detail.candidates


@router.post("/unknowns/{unknown_id:path}/resolve", response_model=ResolveOut)
def resolve_unknown(unknown_id: str, body: ResolveIn):
    return unknowns.resolve(load_snapshot(), unknown_id, body)


@router.get("/unknowns/{unknown_id:path}", response_model=UnknownDetail)
def unknown_detail(unknown_id: str):
    detail = unknowns.get_unknown(load_snapshot(), unknown_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="unknown not found")
    return detail


@router.get("/governance/direct-access", response_model=list[DirectAccessOut])
def governance_direct_access():
    return governance.direct_access(load_snapshot(), rules().get("governance"))


@router.get("/governance/summary", response_model=GovernanceSummary)
def governance_summary():
    return governance.summary(load_snapshot(), rules().get("governance"))


@router.get("/governance/drift", response_model=list[drift.DriftOut])
def governance_drift(stale_days: int = Query(default=30, ge=1, le=365)):
    return drift.detect(load_snapshot(), stale_days=stale_days)


@router.post("/design-review", response_model=DesignReviewOut)
def post_design_review(body: DesignReviewIn):
    result = design_review.review(load_snapshot(), body, rules().get("design_review"))
    if body.use_llm and settings.llm_enabled:
        text, model = llm.explain(body, result)
        result.llmExplanation = text
        result.llmModel = model
    return result
