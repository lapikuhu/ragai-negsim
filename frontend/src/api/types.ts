import type { components, paths } from "@/api/generated/schema";

export type ApiPaths = paths;
export type ApiComponents = components;

export type UserRead = components["schemas"]["UserRead"];
export type Token = components["schemas"]["Token"];
export type SimulationRead = components["schemas"]["SimulationRead"];
export type EvidenceLedger = components["schemas"]["SimulationEvidenceLedgerRead"];
export type SimulationReadWithState = components["schemas"]["SimulationReadWithState"] & {
  evidence_ledgers?: EvidenceLedger[];
};
export type SimulationTokenUsage = {
  simulation_total?: number | null;
  coach_total?: number | null;
  counterpart_latest?: number | null;
  proxy_latest?: number | null;
  evaluator_total?: number | null;
};
export type SimulationEvaluationListItem = SimulationRead & {
  scenario_name?: string | null;
  participant_user_id: number;
};
export type SimulationEvaluationListResponse = {
  items: SimulationEvaluationListItem[];
  skip: number;
  limit: number;
  has_more: boolean;
};
export type SimulationTurnResponse = components["schemas"]["SimulationTurnResponse"] & {
  token_usage?: SimulationTokenUsage;
  evidence_ledgers?: EvidenceLedger[];
};
export type SimulationProxyTurnRequest = {
  persona_id: number | null;
  duration: "this_turn" | "remainder";
  proxy_llm_provider?: LLMProvider | null;
  proxy_llm_model?: string | null;
};
export type SimulationProxyTurnResponse = SimulationTurnResponse & {
  proxy_response: string;
  auto_user_proxy_enabled: boolean;
  user_proxy_persona: Record<string, unknown>;
};
export type SimulationProxyDisableResponse = {
  simulation_id: number;
  status: string;
  auto_user_proxy_enabled: boolean;
  user_proxy_persona: Record<string, unknown>;
  messages: components["schemas"]["SimulationMessageSchema"][];
};
export type LearnerChatMessage = {
  role: "user" | "assistant";
  content: string;
  debug_trace?: unknown;
  tool_calls?: string[];
  token_usage?: { total_tokens: number };
};
export type SimulationLearnerAskRequest = {
  query: string;
  context?: Record<string, unknown>;
  chat_history?: LearnerChatMessage[];
  max_results?: number;
  include_images?: boolean;
  include_answers?: boolean;
  learner_llm_provider?: LLMProvider | null;
  learner_llm_model?: string | null;
};
export type SimulationLearnerAskResponse = {
  simulation_id: number;
  status: string;
  answer: string;
  metadata: Record<string, unknown>;
  timestamp: string;
};
export type LLMProvider = "openai" | "ollama";
export type LLMSelection = {
  provider: LLMProvider;
  model: string;
};
export type LLMModelCatalogItem = {
  name: string;
  size_gib?: number | null;
};
export type LLMProviderCatalog = {
  provider: LLMProvider;
  models: LLMModelCatalogItem[];
  error?: string | null;
};
export type LLMModelCatalogResponse = {
  providers: LLMProviderCatalog[];
  gpu_memory_gib?: number | null;
};
export type SimulationStartRequest = {
  side_a: Record<string, unknown>;
  side_b: Record<string, unknown>;
  max_turn_count: number;
  counterpart_llm_provider?: LLMProvider | null;
  counterpart_llm_model?: string | null;
  evaluator_llm_provider?: LLMProvider | null;
  evaluator_llm_model?: string | null;
};
export type SimulationCreateRequest = components["schemas"]["SimulationCreateRequest"] & {
  use_learner_agent?: boolean;
  learner_response_llm_provider?: LLMProvider | null;
  learner_response_llm_model?: string | null;
  learner_summary_llm_provider?: LLMProvider | null;
  learner_summary_llm_model?: string | null;
  learner_tavily_summary_llm_provider?: LLMProvider | null;
  learner_tavily_summary_llm_model?: string | null;
  learner_tavily_max_results?: number;
  learner_tavily_include_images?: boolean;
  learner_tavily_include_answers?: boolean;
};
export type SessionRead = components["schemas"]["SessionRead"];
export type CorpusRead = components["schemas"]["CorpusRead"];
export type CorpusIndexRead = components["schemas"]["CorpusIndexReadWithIds"];
export type ChunkingProfileRead = components["schemas"]["ChunkingProfileReadWithIds"];
export type RagProfileRead = components["schemas"]["RagProfileReadWithIds"] & {
  knowledge_graph_index_id?: number | null;
};
export type VectorStoreRead = components["schemas"]["VectorStoreReadWithIds"];
export type PromptRead = components["schemas"]["PromptRead"];
export type ScenarioPublicRead = components["schemas"]["ScenarioPublicReadWithIds"];
export type ScenarioAuthoringRead = components["schemas"]["ScenarioAuthoringReadWithIds"];
export type ScenarioRead = ScenarioPublicRead & {
  description?: string | null;
};
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

export type RagProfileFieldDefinitionRead = {
  name: string;
  kind: "int" | "enum";
  label: string;
  required: boolean;
  default: unknown;
  minimum?: number | null;
  maximum?: number | null;
  help_text?: string | null;
  options: string[];
};

export type RagProfileDefinitionRead = {
  strategy: string;
  label: string;
  fields: RagProfileFieldDefinitionRead[];
};

export type RagProfileCreateRequest = {
  name: string;
  strategy: string;
  config: Record<string, unknown>;
  knowledge_graph_index_id?: number | null;
};

export type RagProfileUpdateRequest = {
  name?: string | null;
  strategy?: string | null;
  config?: Record<string, unknown> | null;
  knowledge_graph_index_id?: number | null;
};

export type RagProfileCopy = {
  name: string;
  strategy?: string | null;
  config?: Record<string, unknown> | null;
  knowledge_graph_index_id?: number | null;
};

export type KnowledgeGraphBuildConfig = {
  llm_provider: LLMProvider;
  llm_model: string;
  embedding_provider?: string;
  embedding_model: string;
  extractors: Array<"simple" | "implicit" | "schema">;
  strict_schema?: boolean;
  max_paths_per_chunk?: number;
  ollama_base_url?: string;
};

export type KnowledgeGraphIndexRead = {
  id: number;
  name: string;
  corpus_index_id: number;
  build_config: KnowledgeGraphBuildConfig;
  status: string;
  active_generation?: string | null;
  latest_build_error?: string | null;
  locked_at?: string | null;
  built_at?: string | null;
  created_at: string;
  last_updated: string;
  rag_profile_ids: number[];
  simulation_ids: number[];
  active_job_id?: number | null;
};

export type KnowledgeGraphIndexCreate = {
  name: string;
  corpus_index_id: number;
  build_config: KnowledgeGraphBuildConfig;
};

export type KnowledgeGraphBuildJobRead = {
  id: number;
  knowledge_graph_index_id: number;
  status: string;
  stage: string;
  total_chunks: number;
  processed_chunks: number;
  candidate_generation: string;
  failure_detail?: string | null;
};

export type RawDocumentSourceStatus = "available" | "missing" | "changed" | "unverified" | "error";

export type CorpusSummaryRead = {
  id: number;
  name: string;
  description?: string | null;
};

export type RawDocumentRead = {
  id: number;
  name: string;
  description?: string | null;
  document_title?: string | null;
  document_author?: string | null;
  document_date?: string | null;
  source_path: string;
  source_hash?: string | null;
  source_size?: number | null;
  source_mtime?: string | null;
  source_status: RawDocumentSourceStatus;
  uploaded_at: string;
  uploaded_by_user_id: number;
  uploaded_by_username?: string | null;
  parsed_at?: string | null;
  associated_corpora?: CorpusSummaryRead[];
};

type LegacyRawDocumentRead = {
  id: number;
  name: string;
  description?: string | null;
  document_title?: string | null;
  document_author?: string | null;
  document_date?: string | null;
  path?: string;
  source_path?: string;
  source_hash?: string | null;
  source_size?: number | null;
  source_mtime?: string | null;
  source_status?: RawDocumentSourceStatus;
  uploaded_at: string;
  uploaded_by_user_id: number;
  uploaded_by_username?: string | null;
  parsed_at?: string | null;
  associated_corpora?: CorpusSummaryRead[];
};

export function coerceRawDocumentRead(document: LegacyRawDocumentRead): RawDocumentRead {
  return {
    id: document.id,
    name: document.name,
    description: document.description ?? null,
    document_title: document.document_title ?? null,
    document_author: document.document_author ?? null,
    document_date: document.document_date ?? null,
    source_path: document.source_path ?? document.path ?? "",
    source_hash: document.source_hash ?? null,
    source_size: document.source_size ?? null,
    source_mtime: document.source_mtime ?? null,
    source_status: document.source_status ?? "unverified",
    uploaded_at: document.uploaded_at,
    uploaded_by_user_id: document.uploaded_by_user_id,
    uploaded_by_username: document.uploaded_by_username ?? null,
    parsed_at: document.parsed_at ?? null,
    associated_corpora: document.associated_corpora ?? []
  };
}
