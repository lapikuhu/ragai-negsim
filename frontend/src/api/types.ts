import type { components, paths } from "@/api/generated/schema";

export type ApiPaths = paths;
export type ApiComponents = components;

export type UserRead = components["schemas"]["UserRead"];
export type Token = components["schemas"]["Token"];
export type SimulationRead = components["schemas"]["SimulationRead"];
export type SimulationReadWithState = components["schemas"]["SimulationReadWithState"];
export type SimulationTurnResponse = components["schemas"]["SimulationTurnResponse"];
export type SessionRead = components["schemas"]["SessionRead"];
export type CorpusRead = components["schemas"]["CorpusRead"];
export type CorpusIndexRead = components["schemas"]["CorpusIndexReadWithIds"];
export type ChunkingProfileRead = components["schemas"]["ChunkingProfileReadWithIds"];
export type VectorStoreRead = components["schemas"]["VectorStoreReadWithIds"];
export type PromptRead = components["schemas"]["PromptRead"];
export type ScenarioPublicRead = components["schemas"]["ScenarioPublicReadWithIds"];
export type ScenarioAuthoringRead = components["schemas"]["ScenarioAuthoringReadWithIds"];
export type ScenarioRead = ScenarioPublicRead;
export type ScenarioContextGenerateRequest = components["schemas"]["ScenarioContextGenerateRequest"];
export type ScenarioContextGenerateResponse = components["schemas"]["ScenarioContextGenerateResponse"];
export type CounterpartPersonaRead = components["schemas"]["CounterpartPersonaReadWithIds"];
export type EmbeddingModelRead = components["schemas"]["EmbeddingModelRead"];
export type IndexingJobCreate = components["schemas"]["IndexingJobCreate"];
export type IndexingJobQueued = components["schemas"]["IndexingJobQueued"];
export type IndexingJobDetail = components["schemas"]["IndexingJobDetail"];
export type IndexingJobWarningRead = components["schemas"]["IndexingJobWarningRead"];

export type ChunkerFieldDefinitionRead = {
  name: string;
  kind: "int" | "string" | "string_list";
  label: string;
  required: boolean;
  default: unknown;
  minimum?: number | null;
  maximum?: number | null;
  help_text?: string | null;
};

export type ChunkerDefinitionRead = {
  strategy: string;
  label: string;
  supports_ingestion: boolean;
  fields: ChunkerFieldDefinitionRead[];
};

export type RawDocumentSourceStatus = "available" | "missing" | "changed" | "unverified" | "error";

export type RawDocumentRead = {
  id: number;
  name: string;
  description?: string | null;
  source_path: string;
  source_hash?: string | null;
  source_size?: number | null;
  source_mtime?: string | null;
  source_status: RawDocumentSourceStatus;
  uploaded_at: string;
  uploaded_by_user_id: number;
  parsed_at?: string | null;
};

type LegacyRawDocumentRead = {
  id: number;
  name: string;
  description?: string | null;
  path?: string;
  source_path?: string;
  source_hash?: string | null;
  source_size?: number | null;
  source_mtime?: string | null;
  source_status?: RawDocumentSourceStatus;
  uploaded_at: string;
  uploaded_by_user_id: number;
  parsed_at?: string | null;
};

export function coerceRawDocumentRead(document: LegacyRawDocumentRead): RawDocumentRead {
  return {
    id: document.id,
    name: document.name,
    description: document.description ?? null,
    source_path: document.source_path ?? document.path ?? "",
    source_hash: document.source_hash ?? null,
    source_size: document.source_size ?? null,
    source_mtime: document.source_mtime ?? null,
    source_status: document.source_status ?? "unverified",
    uploaded_at: document.uploaded_at,
    uploaded_by_user_id: document.uploaded_by_user_id,
    parsed_at: document.parsed_at ?? null
  };
}
