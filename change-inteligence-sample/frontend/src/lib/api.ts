import type {
  ChangeType, DesignReviewOut, DirectAccess, Drift, GovernanceSummary, GraphOut, ImpactOut, ObjectDetail, ObjectRef,
  ResolveOut, UnknownDetail, UnknownSummary,
} from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/backend/${path}`, { ...init, headers: { "content-type": "application/json", ...(init?.headers ?? {}) }, cache: "no-store" });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

const enc = encodeURIComponent;

export const api = {
  objects: (params?: { type?: string[]; q?: string }) => {
    const qs = new URLSearchParams();
    params?.type?.forEach((t) => qs.append("type", t));
    if (params?.q) qs.set("q", params.q);
    const s = qs.toString();
    return call<ObjectRef[]>(`api/objects${s ? `?${s}` : ""}`);
  },
  object: (id: string) => call<ObjectDetail>(`api/objects/${enc(id)}`),
  graph: (id: string, depth = 2, includeResolved = false) =>
    call<GraphOut>(`api/objects/${enc(id)}/graph?depth=${depth}&include_resolved=${includeResolved}`),
  impact: (objectId: string, changeType: ChangeType) =>
    call<ImpactOut>(`api/impact?object_id=${enc(objectId)}&change_type=${changeType}`),
  unknowns: (status: "open" | "resolved" | "all" = "open") => call<UnknownSummary[]>(`api/unknowns?status=${status}`),
  unknown: (id: string) => call<UnknownDetail>(`api/unknowns/${enc(id)}`),
  resolve: (id: string, body: { target_id?: string; new_object?: { type: "Service" | "Batch"; name: string; system?: string; team_id?: string }; note?: string }) =>
    call<ResolveOut>(`api/unknowns/${enc(id)}/resolve`, { method: "POST", body: JSON.stringify(body) }),
  directAccess: () => call<DirectAccess[]>("api/governance/direct-access"),
  governance: () => call<GovernanceSummary>("api/governance/summary"),
  drift: (staleDays = 30) => call<Drift[]>(`api/governance/drift?stale_days=${staleDays}`),
  designReview: (body: { name: string; description: string; fields: string[]; system?: string; use_llm?: boolean }) =>
    call<DesignReviewOut>("api/design-review", { method: "POST", body: JSON.stringify(body) }),
};

export const TYPE_COLORS: Record<string, string> = {
  Team: "#8b5cf6",
  Service: "#2563eb",
  API: "#0891b2",
  BusinessObject: "#16a34a",
  Database: "#78716c",
  Table: "#ca8a04",
  Batch: "#db2777",
  Unknown: "#ea580c",
};

export const TYPE_LABELS: Record<string, string> = {
  Team: "担当チーム",
  Service: "アプリケーション",
  API: "API",
  BusinessObject: "業務データ",
  Database: "データベース",
  Table: "テーブル",
  Batch: "バッチ処理",
  Unknown: "未特定",
};

// Relation types -> business wording. Codes stay in tooltips for engineers.
export const REL_LABELS: Record<string, string> = {
  OWNS: "責任を持つ",
  PROVIDES: "提供する",
  CALLS: "呼び出す",
  READS: "参照する",
  WRITES: "更新する",
  OPERATES_ON: "操作対象",
  REPRESENTS: "実体",
  DEPENDS_ON: "依存する",
};
export const relLabel = (t: string) => REL_LABELS[t] ?? t;

export const RISK_LABELS: Record<string, string> = { HIGH: "高", MEDIUM: "中", LOW: "低" };
export const STATUS_LABELS: Record<string, string> = { open: "未特定", resolved: "特定済み", all: "すべて" };
export const ACCESS_LABELS: Record<string, string> = { owner: "正規（責任システム）", direct: "直接参照" };
export const OBS_LABELS: Record<string, string> = { declared: "申告", observed: "観測", manual: "手入力" };
export const SOURCE_LABELS: Record<string, string> = {
  db_query_log: "DB クエリログ", api_gateway_log: "API ゲートウェイログ", openapi: "API 仕様書", network_flow: "ネットワーク通信ログ",
  service_catalog: "サービスカタログ", manual: "手入力",
};
export const DRIFT_LABELS: Record<string, { label: string; hint: string }> = {
  stale: { label: "観測が途絶えている", hint: "ログに現れなくなった依存。使われていなければ廃止候補" },
  observed_only: { label: "申告のない利用", hint: "ログでは使っているのに台帳に申告がない（影の依存）" },
  declared_only: { label: "使われていない申告", hint: "申告はあるがログに一度も現れない" },
  no_evidence: { label: "根拠なし", hint: "ログも申告もない関係" },
  unknown_open: { label: "未特定のまま", hint: "正体不明の利用元が長期間放置されている" },
};
export const UNKNOWN_TYPE_LABELS: Record<string, string> = { consumer: "利用元", owner: "責任者", target: "参照先" };
export const CHANGE_LABELS: Record<string, { label: string; hint: string }> = {
  schema_change: { label: "テーブル／項目の変更", hint: "項目の追加・変更・削除の影響を見る" },
  api_change: { label: "API の変更", hint: "呼び出している側への影響を見る" },
  delete: { label: "廃止（削除）", hint: "廃止してよいかを確認する" },
};
export const PROP_LABELS: Record<string, string> = {
  name: "名称", description: "説明", system: "所属システム", criticality: "重要度", repository: "リポジトリ",
  method: "メソッド", path: "パス", version: "バージョン", engine: "DB 種別", environment: "環境",
  database: "データベース", schema: "スキーマ", columns: "項目（カラム）", schedule: "実行スケジュール",
  unknown_type: "種別", status: "状態", hint: "手がかり", access_mode: "アクセス種別", observation_type: "把握方法",
  note: "補足", resolved_from: "特定前の ID", resolved_to: "特定先", resolved_at: "特定日時", resolve_note: "特定メモ",
};
export const propLabel = (k: string) => PROP_LABELS[k] ?? k;
export function propValue(k: string, v: unknown): string {
  if (Array.isArray(v)) return v.join(", ");
  const sv = String(v);
  if (k === "access_mode") return ACCESS_LABELS[sv] ?? sv;
  if (k === "observation_type") return OBS_LABELS[sv] ?? sv;
  if (k === "status") return STATUS_LABELS[sv] ?? sv;
  if (k === "unknown_type") return UNKNOWN_TYPE_LABELS[sv] ?? sv;
  return sv;
}
