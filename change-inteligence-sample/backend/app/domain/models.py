"""Pydantic response/request models for the API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ChangeType = Literal["schema_change", "api_change", "delete"]


class ObjectRef(BaseModel):
    id: str
    type: str
    name: str


class EvidenceOut(BaseModel):
    id: str
    relation_id: str
    source_type: str | None = None
    source_ref: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    confidence: float | None = None
    observation_type: str | None = None
    resolved_from: str | None = None


class RelationOut(BaseModel):
    id: str
    type: str
    source: ObjectRef
    target: ObjectRef
    direction: Literal["in", "out"]
    properties: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceOut] = Field(default_factory=list)


class ObjectDetail(BaseModel):
    id: str
    type: str
    name: str
    properties: dict[str, Any]
    owners: list[ObjectRef]
    relations: list[RelationOut]


class GraphNode(BaseModel):
    id: str
    type: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    isCenter: bool = False


class GraphEdge(BaseModel):
    id: str
    type: str
    source: str
    target: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphOut(BaseModel):
    center: str
    depth: int
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    unknownCount: int
    truncated: bool = False


class AffectedOut(BaseModel):
    id: str
    type: str
    name: str
    path: list[str]
    via: list[str]
    direct: bool
    depth: int
    owners: list[ObjectRef]
    accessMode: str | None = None
    evidenceCount: int = 0


class ImpactOut(BaseModel):
    target: str
    targetName: str
    targetType: str
    changeType: ChangeType
    risk: Literal["LOW", "MEDIUM", "HIGH"]
    affected: list[AffectedOut]
    owners: list[str]
    ownerDetails: list[ObjectRef]
    unknownCount: int
    warnings: list[str]
    canDelete: bool | None = None
    summary: str


class UnknownSummary(BaseModel):
    id: str
    name: str
    unknown_type: str | None = None
    status: str
    hint: str | None = None
    relationCount: int
    evidenceCount: int
    lastSeen: str | None = None
    resolvedTo: str | None = None


class UnknownDetail(UnknownSummary):
    relations: list[RelationOut]
    evidence: list[EvidenceOut]
    candidates: list[ObjectRef]


class NewObjectIn(BaseModel):
    type: Literal["Service", "Batch"]
    name: str
    id: str | None = None
    system: str | None = None
    team_id: str | None = None


class ResolveIn(BaseModel):
    target_id: str | None = None
    new_object: NewObjectIn | None = None
    note: str | None = None


class ResolveOut(BaseModel):
    unknown: UnknownSummary
    resolvedTo: ObjectRef
    movedRelations: int
    inheritedEvidence: int


class DirectAccessOut(BaseModel):
    relationId: str
    relation: str
    source: ObjectRef
    sourceOwners: list[ObjectRef]
    target: ObjectRef
    targetOwners: list[ObjectRef]
    accessMode: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    bypassesApi: bool
    canonicalApis: list[ObjectRef]
    note: str | None = None
    evidence: list[EvidenceOut]


class GovernanceSummary(BaseModel):
    directAccessCount: int
    directAccessBySeverity: dict[str, int]
    ownerMissing: list[ObjectRef]
    unknownOpen: int
    unknownResolved: int
    objectCount: int
    relationCount: int


class DesignReviewIn(BaseModel):
    name: str
    description: str = ""
    fields: list[str] = Field(default_factory=list)
    system: str | None = None
    use_llm: bool = True


class CandidateOut(BaseModel):
    id: str
    type: str
    name: str
    score: float
    matchedFields: list[str]
    missingFields: list[str]
    extraFields: list[str]
    owners: list[ObjectRef]
    apis: list[ObjectRef]
    consumers: list[ObjectRef]
    representedBy: list[ObjectRef]
    reasons: list[str]


class DesignReviewOut(BaseModel):
    recommendation: Literal["REUSE", "EXTEND", "CREATE"]
    confidence: float
    rationale: list[str]
    alternatives: list[dict[str, str]]
    candidates: list[CandidateOut]
    consult: list[ObjectRef]
    llmExplanation: str | None = None
    llmModel: str | None = None
