# FRONTEND.md: Next.js App Specification

Stack: Next.js (App Router) · TypeScript (strict) · Tailwind CSS · shadcn/ui · TanStack Query · `react-pdf` (Phase 4)

---

## 1. Goals

- ChatGPT-style two-pane interface: documents on the left, chat on the right.
- Make **grounding visible**: citations, source drawer, and a clearly distinct refusal state.
- Fast, accessible, and resilient (upload progress, processing status, errors).

---

## 2. Project Structure

```
frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx                     # redirects to /chat
│   ├── chat/
│   │   ├── page.tsx                 # new chat
│   │   └── [conversationId]/page.tsx
│   ├── (auth)/login/page.tsx        # Phase 3
│   └── globals.css
├── components/
│   ├── documents/
│   │   ├── DocumentSidebar.tsx
│   │   ├── UploadDropzone.tsx
│   │   ├── DocumentListItem.tsx
│   │   └── StatusBadge.tsx
│   ├── chat/
│   │   ├── ChatWindow.tsx
│   │   ├── MessageList.tsx
│   │   ├── MessageBubble.tsx
│   │   ├── AnswerText.tsx           # parses [n] into CitationBadge
│   │   ├── CitationBadge.tsx
│   │   ├── SourceDrawer.tsx
│   │   ├── RefusalNotice.tsx
│   │   ├── Composer.tsx
│   │   └── FeedbackButtons.tsx
│   ├── preview/PdfViewer.tsx        # Phase 4
│   └── ui/                          # shadcn components
├── lib/
│   ├── api.ts                       # fetch wrapper (auth header, error mapping)
│   ├── api-types.ts                 # generated from OpenAPI
│   ├── sse.ts                       # stream reader (Phase 4)
│   └── citations.ts                 # parse/split [n] markers
├── hooks/
│   ├── useDocuments.ts              # list + polling + upload + delete
│   ├── useChat.ts                   # send question, optimistic update
│   ├── useConversations.ts
│   └── useSelectedDocuments.ts
├── tests/                           # vitest + testing-library
└── e2e/                             # playwright
```

---

## 3. Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ Header: Document Q&A            Searching in: OS.pdf, DBMS.pdf       │
├────────────────────┬─────────────────────────────────────────────────┤
│ Documents          │ Chat                                            │
│ [+ Upload]         │                                                 │
│ ☑ OS.pdf      ✓    │  You: What is a process?                        │
│ ☐ DBMS.pdf    ✓    │  Bot: A process is a program in execution. [1]  │
│ ☐ New.pdf     ⏳   │       Sources: [1] OS.pdf · p.12                │
│                    │                                                 │
│ Conversations      │  You: Who invented Python?                      │
│  • What is a proc… │  ⓘ I couldn't find the answer in the uploaded   │
│  • Deadlock       │     documents.                                  │
│                    │ ───────────────────────────────────────────── │
│                    │ [ Ask a question…                          ➤ ]  │
└────────────────────┴─────────────────────────────────────────────────┘
```
- Mobile (< 768px): sidebar becomes a slide-over sheet; the source drawer becomes a bottom sheet.

---

## 4. Components

### 4.1 `DocumentSidebar`
- Lists documents (`useDocuments`), each with checkbox, filename, `StatusBadge`, delete menu.
- Checkbox disabled unless `status === "ready"`.
- Polls `GET /documents` every 2 s **only while any document is `uploaded`/`processing`** (`refetchInterval` function returns `false` otherwise).
- Delete: confirm dialog; on success invalidate the list and remove from the selection.

### 4.2 `UploadDropzone`
- Drag-drop + click; accepts `.pdf,.docx,.txt,.md`; client-side check of type and size (mirrors server; server is authoritative).
- Shows per-file upload progress (XHR/`fetch` with progress or indeterminate), then transitions to a `processing` badge.
- Errors mapped from API codes: `INVALID_FILE_TYPE`, `FILE_TOO_LARGE`, `DUPLICATE_DOCUMENT`, `RATE_LIMITED`.

### 4.3 `StatusBadge`
| Status | Visual |
|---|---|
| uploaded / processing | spinner + "Processing…" |
| ready | green check |
| failed | red alert with tooltip showing `error_message` (e.g. "No extractable text") |

### 4.4 `ChatWindow`
- Holds messages for the active conversation; auto-scrolls to the newest message unless the user scrolled up.
- `Composer` disabled with helper text when no **ready** document is selected: "Select at least one processed document to start."
- Enter to send, Shift+Enter for newline; input limited to 2000 chars with counter near the limit.

### 4.5 `MessageBubble`
- **User**: right-aligned plain text.
- **Assistant, grounded**: `AnswerText` + sources list + `FeedbackButtons`.
- **Assistant, refusal** (`grounded === false`): `RefusalNotice`.

### 4.6 `AnswerText` and `CitationBadge`
- `lib/citations.ts` splits the answer by `/\[(\d+)\]/` into text and citation nodes.
- `CitationBadge` renders `[n]` as a small clickable chip; hover shows document + page; click opens `SourceDrawer` focused on source `n`.
- If a marker references a non-existent source (shouldn't happen, backend validates), render as plain text.

### 4.7 `SourceDrawer`
Shows for each source: document name, page (range), and the snippet with the cited text. Buttons: "Open document" (Phase 4: opens `PdfViewer` at the page with the snippet highlighted).

### 4.8 `RefusalNotice`
- Neutral (not red/error) styling: info icon, muted background, the refusal text.
- No sources, no thumbs (or thumbs available to report a wrong refusal; optional).
- Optional hint: "Try rephrasing, or select other documents." Keep it static; never generated by the model.

### 4.9 `FeedbackButtons`
Thumbs up/down, optimistic update, calls `POST /messages/{id}/feedback`.

---

## 5. State & Data Fetching

| State | Where |
|---|---|
| Documents, conversations, messages | TanStack Query (server state) |
| Selected document IDs | `useSelectedDocuments`: persisted in `localStorage` and synced to a `?docs=` query param |
| Active conversation | URL param `/chat/[conversationId]` |
| Composer text, drawer open | component state |

### Query keys
`["documents"]`, `["conversations"]`, `["messages", conversationId]`.

### Sending a question (non-streaming, V1)
1. Optimistically append the user message + a "thinking" placeholder.
2. `POST /chat`; on success replace the placeholder with the assistant message; set `conversation_id` in the URL if new.
3. On error: replace the placeholder with an error bubble + **Retry** button (never show a fake answer).

### Streaming (Phase 4)
`lib/sse.ts` reads `text/event-stream` with `fetch` + `ReadableStream` (EventSource can't send auth headers). Handle `meta`, `token`, `done`, `refusal`, `error`. Because the backend streams only after gates pass, tokens are safe to render as they arrive. If the connection drops, refetch messages.

---

## 6. API Client (`lib/api.ts`)

- Base URL from `NEXT_PUBLIC_API_URL`; attaches `Authorization` when a session exists.
- Parses the standard error format into `ApiError { code, message, status }`.
- 401 → redirect to login (Phase 3). 429 → show toast with `Retry-After`.
- Types generated with `openapi-typescript` into `api-types.ts` (`npm run gen:api`).

---

## 7. Empty, Loading and Error States

| Situation | UI |
|---|---|
| No documents | Big dropzone: "Upload a PDF, DOCX, TXT or MD to get started" |
| Docs ready, no messages | Suggested prompts ("Summarize the main topics", "What does section 2 say about…") as static chips |
| Upload failed | Inline error under the file with a retry |
| Doc `failed` | Red badge + tooltip; hint to re-upload (or OCR note for scanned files) |
| Chat request failed | Error bubble + Retry |
| Selected doc deleted | Removed from selection; toast |
| Offline | Banner: "You're offline" |

---

## 8. Accessibility & UX Quality

- All interactive elements keyboard reachable; visible focus rings.
- ARIA: chat log `role="log"` `aria-live="polite"`; drawer `role="dialog"` with focus trap; badges have `aria-label="Source 1: OS.pdf page 12"`.
- Color contrast AA; don't rely on color alone for status (icons + text).
- Respect `prefers-reduced-motion` and dark mode (Tailwind `dark:`).
- Render answers as text (no `dangerouslySetInnerHTML`). If Markdown rendering is added, sanitize.

---

## 9. Testing

- **Unit (vitest + RTL):** `citations.ts` parsing, `AnswerText` rendering, `StatusBadge`, `Composer` disabled logic, `useDocuments` polling behavior.
- **E2E (Playwright, Phase 4):** upload fixture PDF → wait for ready → ask in-scope question → see citation → open drawer → ask out-of-scope question → see refusal (no sources).
- Mock the API with MSW for component tests.

---

## 10. Environment

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_MAX_UPLOAD_MB=25
```
