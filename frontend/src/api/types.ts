import type { components, paths } from "@/api/generated/schema";

export type ApiPaths = paths;
export type ApiComponents = components;

export type UserRead = components["schemas"]["UserRead"];
export type Token = components["schemas"]["Token"];
export type SimulationRead = components["schemas"]["SimulationRead"];
export type SimulationReadWithState = components["schemas"]["SimulationReadWithState"];
export type SimulationTurnResponse = components["schemas"]["SimulationTurnResponse"];
export type SessionRead = components["schemas"]["SessionRead"];
export type RawDocumentRead = components["schemas"]["RawDocumentRead"];
export type CorpusRead = components["schemas"]["CorpusRead"];
export type CorpusIndexRead = components["schemas"]["CorpusIndexReadWithIds"];
export type ChunkingProfileRead = components["schemas"]["ChunkingProfileReadWithIds"];
export type VectorStoreRead = components["schemas"]["VectorStoreReadWithIds"];
export type PromptRead = components["schemas"]["PromptRead"];
export type ScenarioRead = components["schemas"]["ScenarioReadWithIds"];
export type CounterpartPersonaRead = components["schemas"]["CounterpartPersonaReadWithIds"];
export type EmbeddingModelRead = components["schemas"]["EmbeddingModelRead"];
