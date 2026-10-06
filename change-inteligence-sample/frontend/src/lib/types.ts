export type ObjectRef = { id: string; type: string; name: string };

export type EvidenceOut = {
  id: string;
  relation_id: string;
  source_type?: string | null;
  source_ref?: string | null;
  first_seen?: string | null;
  last_seen?: string | null;
  confidence?: number | null;
  observation_type?: string | null;
  resolved_from?: string | null;
};

export type RelationOut = {
  id: string;
  type: string;
  source: ObjectRef;
  target: ObjectRef;
  direction: "in" | "out";
  properties: Record<string, unknown>;
  evidence: EvidenceOut[];
};

export type ObjectDetail = {
  id: string;
  type: string;
  name: string;
  properties: Record<string, unknown>;
  owners: ObjectRef[];
  relations: RelationOut[];
};

export type GraphNode = { id: string; type: string; name: string; properties: Record<string, unknown>; isCenter: boolean };
export type GraphEdge = { id: string; type: string; source: string; target: string; properties: Record<string, unknown> };
export type GraphOut = { center: string; depth: number; nodes: GraphNode[]; edges: GraphEdge[]; unknownCount: number; truncated: boolean };

export type Affected = {
  id: string; type: string; name: string; path: string[]; via: string[]; direct: boolean; depth: number;
  owners: ObjectRef[]; accessMode?: string | null; evidenceCount: number;
};
export type ChangeType = "schema_change" | "api_change" | "delete";
export type ImpactOut = {
  target: string; targetName: string; targetType: string; changeType: ChangeType; risk: "LOW" | "MEDIUM" | "HIGH";
  affected: Affected[]; owners: string[]; ownerDetails: ObjectRef[]; unknownCount: number; warnings: string[];
  canDelete: boolean | null; summary: string;
};

export type UnknownSummary = {
  id: string; name: string; unknown_type?: string | null; status: string; hint?: string | null;
  relationCount: number; evidenceCount: number; lastSeen?: string | null; resolvedTo?: string | null;
};
export type UnknownDetail = UnknownSummary & { relations: RelationOut[]; evidence: EvidenceOut[]; candidates: ObjectRef[] };
export type ResolveOut = { unknown: UnknownSummary; resolvedTo: ObjectRef; movedRelations: number; inheritedEvidence: number };

export type DirectAccess = {
  relationId: string; relation: string; source: ObjectRef; sourceOwners: ObjectRef[]; target: ObjectRef; targetOwners: ObjectRef[];
  accessMode: string; severity: "LOW" | "MEDIUM" | "HIGH"; bypassesApi: boolean; canonicalApis: ObjectRef[]; note?: string | null;
  evidence: EvidenceOut[];
};
export type GovernanceSummary = {
  directAccessCount: number; directAccessBySeverity: Record<string, number>; ownerMissing: ObjectRef[];
  unknownOpen: number; unknownResolved: number; objectCount: number; relationCount: number;
};

export type Candidate = {
  id: string; type: string; name: string; score: number; matchedFields: string[]; missingFields: string[]; extraFields: string[];
  owners: ObjectRef[]; apis: ObjectRef[]; consumers: ObjectRef[]; representedBy: ObjectRef[]; reasons: string[];
};
export type DesignReviewOut = {
  recommendation: "REUSE" | "EXTEND" | "CREATE"; confidence: number; rationale: string[];
  alternatives: { recommendation: string; reason: string }[]; candidates: Candidate[]; consult: ObjectRef[];
  llmExplanation?: string | null; llmModel?: string | null;
};

export type DriftKind = "stale" | "declared_only" | "observed_only" | "no_evidence" | "unknown_open";
export type Drift = {
  kind: DriftKind; severity: "LOW" | "MEDIUM" | "HIGH"; title: string; detail: string;
  relationId?: string | null; relation?: string | null; source?: ObjectRef | null; target?: ObjectRef | null;
  lastSeen?: string | null; daysSince?: number | null; notify: ObjectRef[];
};
