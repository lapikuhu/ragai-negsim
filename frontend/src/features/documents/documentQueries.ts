import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, ApiError, apiFetch, unwrapResult } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import { coerceRawDocumentRead, type ApiComponents, type RawDocumentRead } from "@/api/types";

type RawDocumentChunkResult = ApiComponents["schemas"]["RawDocumentChunkResult"];
type RawDocumentIngestResult = ApiComponents["schemas"]["RawDocumentIngestResult"];
type RawDocumentUpdate = Pick<
  ApiComponents["schemas"]["RawDocumentUpdate"],
  "name" | "description" | "document_title" | "document_author" | "document_year"
>;

export const documentKeys = {
  all: ["documents"] as const,
  detail: (documentId: number) => ["documents", documentId] as const
};

export type RawDocumentUploadInput = {
  name: string;
  description?: string;
  documentTitle?: string;
  documentAuthor?: string;
  documentYear?: number;
  corpusIds: number[];
  file: File;
};

export type RawDocumentUpdateInput = RawDocumentUpdate;

export async function listDocuments() {
  const result = await apiClient.GET("/raw-documents/", { params: { query: { skip: 0, limit: 50 } } });
  return unwrapResult(result, "Unable to load documents").map(coerceRawDocumentRead);
}

export async function getDocument(documentId: number) {
  const result = await apiClient.GET("/raw-documents/{raw_document_id}", {
    params: { path: { raw_document_id: documentId } }
  });
  return coerceRawDocumentRead(unwrapResult(result, "Unable to load document"));
}

async function uploadDocument(input: RawDocumentUploadInput) {
  const form = new FormData();
  form.set("name", input.name);
  if (input.description) {
    form.set("description", input.description);
  }
  if (input.documentTitle) {
    form.set("document_title", input.documentTitle);
  }
  if (input.documentAuthor) {
    form.set("document_author", input.documentAuthor);
  }
  if (input.documentYear !== undefined) {
    form.set("document_year", String(input.documentYear));
  }
  input.corpusIds.forEach((id) => form.append("corpus_ids", String(id)));
  form.set("file", input.file);

  const response = await apiFetch(`${getApiBaseUrl()}/raw-documents/`, {
    method: "POST",
    body: form
  });
  const payload = await response.text();

  if (!response.ok) {
    let detail: unknown = payload;
    try {
      detail = JSON.parse(payload);
    } catch {
      // Keep plain-text payload when the backend does not return JSON.
    }
    throw new ApiError("Unable to upload document", response.status, detail);
  }

  return coerceRawDocumentRead(JSON.parse(payload));
}

async function ingestDocument(documentId: number, profileId: number) {
  const result = await apiClient.POST("/raw-documents/{raw_document_id}/chunking-profiles/{profile_id}/ingest", {
    params: { path: { raw_document_id: documentId, profile_id: profileId } }
  });
  return unwrapResult<RawDocumentIngestResult>(result, "Unable to ingest document");
}

async function chunkDocument(documentId: number, profileId: number) {
  const result = await apiClient.POST("/raw-documents/{raw_document_id}/chunking-profiles/{profile_id}/chunk", {
    params: { path: { raw_document_id: documentId, profile_id: profileId } }
  });
  return unwrapResult<RawDocumentChunkResult>(result, "Unable to chunk document");
}

async function updateDocument(documentId: number, input: RawDocumentUpdateInput) {
  const result = await apiClient.PATCH("/raw-documents/{raw_document_id}", {
    params: { path: { raw_document_id: documentId } },
    body: input
  });
  return coerceRawDocumentRead(unwrapResult(result, "Unable to update document"));
}

export function useDocumentsQuery() {
  return useQuery({ queryKey: documentKeys.all, queryFn: listDocuments });
}

export function useDocumentDetailQuery(documentId: number) {
  return useQuery({
    queryKey: documentKeys.detail(documentId),
    queryFn: () => getDocument(documentId),
    enabled: Number.isFinite(documentId)
  });
}

function useInvalidateDocuments() {
  const queryClient = useQueryClient();
  return async (documentId?: number) => {
    await queryClient.invalidateQueries({ queryKey: documentKeys.all });
    if (typeof documentId === "number") {
      await queryClient.invalidateQueries({ queryKey: documentKeys.detail(documentId) });
    }
  };
}

export function useUploadDocumentMutation() {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: uploadDocument,
    onSuccess: async (document) => invalidate(document.id)
  });
}

export function useIngestDocumentMutation(documentId: number) {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: (profileId: number) => ingestDocument(documentId, profileId),
    onSuccess: async () => invalidate(documentId)
  });
}

export function useChunkDocumentMutation(documentId: number) {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: (profileId: number) => chunkDocument(documentId, profileId),
    onSuccess: async () => invalidate(documentId)
  });
}

export function useUpdateDocumentMutation(documentId: number) {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: (input: RawDocumentUpdateInput) => updateDocument(documentId, input),
    onSuccess: async (document) => invalidate(document.id)
  });
}
