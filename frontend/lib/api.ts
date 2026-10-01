export type DocumentStatus = "uploaded" | "processing" | "ready" | "failed";

export type Source = {
  index: number;
  document_id: string;
  document: string;
  page: number | null;
  page_end: number | null;
  chunk_id: string;
  snippet: string;
};

export type DocumentItem = {
  id: string;
  filename: string;
  file_type: "pdf" | "docx" | "txt" | "md";
  file_size: number;
  page_count: number | null;
  status: DocumentStatus;
  error_message: string | null;
  chunk_count: number | null;
  created_at: string;
};

export type ChatResponse = {
  conversation_id: string;
  message_id: string;
  answer: string;
  grounded: boolean;
  sources: Source[];
  debug?: Record<string, unknown> | null;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    headers: {
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { error?: { message?: string } }
      | null;
    throw new Error(body?.error?.message ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function listDocuments(): Promise<{ items: DocumentItem[] }> {
  return request<{ items: DocumentItem[] }>("/documents");
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const form = new FormData();
  form.append("file", file);
  const response = await request<{
    document_id: string;
    filename: string;
    status: DocumentStatus;
  }>("/documents/upload", { method: "POST", body: form });
  return {
    id: response.document_id,
    filename: response.filename,
    file_type: (response.filename.split(".").pop() ?? "txt") as DocumentItem["file_type"],
    file_size: file.size,
    page_count: null,
    status: response.status,
    error_message: null,
    chunk_count: null,
    created_at: new Date().toISOString(),
  };
}

export async function deleteDocument(id: string): Promise<void> {
  await request<void>(`/documents/${id}`, { method: "DELETE" });
}

export async function askQuestion(
  documentIds: string[],
  question: string,
  conversationId?: string,
): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      document_ids: documentIds,
      question,
      conversation_id: conversationId ?? null,
    }),
  });
}
