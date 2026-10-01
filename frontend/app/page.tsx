"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, LoaderCircle, Plus, Send, Trash2, UploadCloud } from "lucide-react";

import {
  askQuestion,
  deleteDocument,
  DocumentItem,
  listDocuments,
  Source,
  uploadDocument,
} from "../lib/api";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  grounded?: boolean;
  sources?: Source[];
  debug?: Record<string, unknown> | null;
};

const supportedExtensions = ".pdf,.docx,.txt,.md";

export default function HomePage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string>();

  const readySelected = useMemo(
    () => documents.filter((document) => selectedIds.includes(document.id) && document.status === "ready"),
    [documents, selectedIds],
  );

  async function refreshDocuments() {
    try {
      const response = await listDocuments();
      setDocuments(response.items);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load documents");
    }
  }

  useEffect(() => {
    void refreshDocuments();
  }, []);

  useEffect(() => {
    if (!documents.some((document) => document.status === "processing")) return;
    const interval = window.setInterval(() => void refreshDocuments(), 2_000);
    return () => window.clearInterval(interval);
  }, [documents]);

  async function handleUpload(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await uploadDocument(file);
      await refreshDocuments();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id: string) {
    setError(null);
    try {
      await deleteDocument(id);
      setSelectedIds((current) => current.filter((selectedId) => selectedId !== id));
      await refreshDocuments();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Delete failed");
    }
  }

  async function handleAsk(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || readySelected.length === 0 || busy) return;
    setBusy(true);
    setError(null);
    setMessages((current) => [...current, { role: "user", content: trimmedQuestion }]);
    setQuestion("");
    try {
      const response = await askQuestion(
        readySelected.map((document) => document.id),
        trimmedQuestion,
        conversationId,
      );
      setConversationId(response.conversation_id);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.answer,
          grounded: response.grounded,
          sources: response.sources,
          debug: response.debug,
        },
      ]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Question failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="workspace">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">AQ</span><span>Archive Q&A</span></div>
        <label className="upload-zone">
          <UploadCloud size={20} />
          <span>Upload a document</span>
          <small>PDF, DOCX, TXT, or Markdown</small>
          <input type="file" accept={supportedExtensions} onChange={(event) => void handleUpload(event.target.files?.[0])} />
        </label>
        <div className="sidebar-heading"><span>Library</span><span>{documents.length}</span></div>
        <div className="document-list">
          {documents.map((document) => (
            <div className={`document-row ${selectedIds.includes(document.id) ? "selected" : ""}`} key={document.id}>
              <label className="document-select">
                <input
                  type="checkbox"
                  checked={selectedIds.includes(document.id)}
                  disabled={document.status !== "ready"}
                  onChange={() => setSelectedIds((current) => current.includes(document.id) ? current.filter((id) => id !== document.id) : [...current, document.id])}
                />
                <FileText size={17} />
                <span className="document-name">{document.filename}</span>
              </label>
              <button className="icon-button" title="Delete document" aria-label={`Delete ${document.filename}`} onClick={() => void handleDelete(document.id)}>
                <Trash2 size={15} />
              </button>
              <span className={`status status-${document.status}`}>{document.status}</span>
            </div>
          ))}
          {documents.length === 0 && <div className="empty-library">Your library is empty.</div>}
        </div>
        <div className="sidebar-foot">{busy ? <><LoaderCircle className="spin" size={15} /> Working</> : `${readySelected.length} document${readySelected.length === 1 ? "" : "s"} selected`}</div>
      </aside>

      <section className="chat-panel">
        <header className="chat-header"><div><p className="eyebrow">Grounded workspace</p><h1>Ask your archive</h1></div><span className="secure-pill">Evidence only</span></header>
        <div className="messages">
          {messages.length === 0 && <div className="welcome"><div className="welcome-icon"><Plus size={22} /></div><h2>Start with a document</h2><p>Select a ready document, then ask a precise question. Answers stay anchored to the selected evidence.</p></div>}
          {messages.map((message, index) => (
            <article className={`message ${message.role} ${message.grounded === false ? "refusal" : ""}`} key={`${message.role}-${index}`}>
              <div className="message-label">{message.role === "user" ? "You" : message.grounded === false ? "No supporting evidence" : "Archive"}</div>
              <p>{message.content}</p>
              {message.sources && message.sources.length > 0 && <div className="sources">{message.sources.map((source) => <div className="source" key={source.chunk_id}><span>[{source.index}]</span><div><strong>{source.document}</strong><small>Page {source.page ?? "-"}</small><p>{source.snippet}</p></div></div>)}</div>}
              {message.debug && <details className="debug"><summary>Debug trace</summary><pre>{JSON.stringify(message.debug, null, 2)}</pre></details>}
            </article>
          ))}
        </div>
        <form className="composer" onSubmit={(event) => void handleAsk(event)}>
          <textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder={readySelected.length ? "Ask about the selected evidence..." : "Select a ready document to begin"} disabled={!readySelected.length || busy} rows={2} />
          <button className="send-button" type="submit" disabled={!readySelected.length || !question.trim() || busy} title="Send question" aria-label="Send question"><Send size={18} /></button>
        </form>
        {error && <div className="error-banner" role="alert">{error}</div>}
      </section>
    </main>
  );
}
