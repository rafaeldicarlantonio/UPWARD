import { ChatResponse, Mode, ProcessTrace } from './types';

const ensureBaseUrl = (): string => {
  const raw = process.env.NEXT_PUBLIC_API_URL;
  if (!raw || !raw.trim()) {
    throw new Error('NEXT_PUBLIC_API_URL is not configured');
  }
  return raw.endsWith('/') ? raw.slice(0, -1) : raw;
};

const isFormDataBody = (body: BodyInit | null | undefined): body is FormData =>
  typeof FormData !== 'undefined' && body instanceof FormData;

const buildUrl = (path: string): string => {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${ensureBaseUrl()}${normalizedPath}`;
};

const safeParseJson = (text: string): unknown => {
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
};

const extractErrorMessage = (payload: unknown, fallback: string): string => {
  if (payload && typeof payload === 'object') {
    const detail = (payload as Record<string, unknown>).detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    const message = (payload as Record<string, unknown>).message;
    if (typeof message === 'string' && message.trim()) {
      return message;
    }
    const error = (payload as Record<string, unknown>).error;
    if (typeof error === 'string' && error.trim()) {
      return error;
    }
  }
  return fallback;
};

const buildQueryString = (params: Record<string, unknown> = {}): string => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }
    if (Array.isArray(value)) {
      value.forEach((entry) => {
        if (entry !== undefined && entry !== null) {
          search.append(key, String(entry));
        }
      });
      return;
    }
    search.append(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : '';
};

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers ?? undefined);
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  if (options.body && !isFormDataBody(options.body) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(buildUrl(path), {
    ...options,
    headers,
  });

  const text = await response.text();
  const data = safeParseJson(text);

  if (!response.ok) {
    const message = extractErrorMessage(data, `Request failed with status ${response.status}`);
    throw new Error(message);
  }

  return data as T;
}

export interface ChatRequestOptions {
  includeProcessTrace?: boolean;
  includeContradictions?: boolean;
}

export interface ChatRequestPayload {
  sessionId?: string;
  prompt: string;
  mode: Mode;
  options?: ChatRequestOptions;
}

interface UploadIngestSummary {
  memory_id?: string;
  embedding_id?: string;
  [key: string]: unknown;
}

export interface UploadResponse {
  status: string;
  file_name: string;
  file_id?: string | null;
  mime_type?: string | null;
  bytes: number;
  chunks: number;
  ingest: {
    upserted: UploadIngestSummary[];
    updated: UploadIngestSummary[];
    skipped: UploadIngestSummary[];
    raw?: Record<string, unknown>;
  };
  extraction_enabled: boolean;
  extracted_candidates: number;
  autosave: {
    saved: boolean;
    items: Record<string, unknown>[];
    skipped?: Record<string, unknown>[];
  };
  autosave_error?: string | null;
}

export interface MemoryMetadataPayload {
  type: 'semantic' | 'episodic' | 'procedural';
  title?: string;
  text: string;
  tags?: string[];
  roleView?: string[];
  source?: string;
  fileId?: string;
}

export interface MemoryMetadataResponse {
  memory_id?: string;
  embedding_id?: string | null;
}

export interface RecentUpload {
  id: string;
  filename: string;
  sourceType?: string;
  reliability?: 'low' | 'medium' | 'high';
  status?: 'new' | 'under_review' | 'accepted' | 'deprecated';
  uploadedAt?: string;
  metadata?: Record<string, unknown>;
}

interface RecentUploadsResponse {
  items: RecentUpload[];
}

export interface MemoryRecord {
  id: string;
  type?: string;
  title?: string;
  tags?: string[];
  createdAt?: string;
  content?: string;
  metadata?: Record<string, unknown>;
}

export interface RheomodeRun {
  id: string;
  sessionId: string;
  messageId: string;
  role?: string;
  createdAt?: string;
  liftScore?: number;
  contradictionScore?: number;
  processTraceSummary?: ProcessTrace;
  processTrace?: ProcessTrace;
  [key: string]: unknown;
}

export interface ContradictionQueryParams extends Record<string, string | number | undefined> {
  status?: 'open' | 'resolved';
  subject?: string;
  limit?: number;
  offset?: number;
  search?: string;
}

export interface ContradictionRecord {
  id: string;
  subject?: string;
  claimA: string;
  claimB: string;
  status: 'open' | 'resolved';
  confidence?: number;
  evidenceIds?: string[];
  updatedAt?: string;
  createdAt?: string;
}

interface ContradictionsResponse {
  items: ContradictionRecord[];
  total?: number;
}

export async function sendChat(payload: ChatRequestPayload): Promise<ChatResponse> {
  const body: Record<string, unknown> = {
    prompt: payload.prompt,
    session_id: payload.sessionId,
    mode: payload.mode,
    messages: [
      {
        role: 'user',
        content: payload.prompt,
      },
    ],
    preferences: {
      includeProcessTrace: payload.options?.includeProcessTrace ?? false,
      includeContradictions: payload.options?.includeContradictions ?? false,
    },
  };

  return request<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function uploadFile(formData: FormData): Promise<UploadResponse> {
  return request<UploadResponse>('/upload', {
    method: 'POST',
    body: formData,
  });
}

export async function upsertMemoryMetadata(
  payload: MemoryMetadataPayload,
): Promise<MemoryMetadataResponse> {
  const body = {
    type: payload.type,
    title: payload.title,
    text: payload.text,
    tags: payload.tags,
    role_view: payload.roleView,
    source: payload.source,
    file_id: payload.fileId,
  };

  return request<MemoryMetadataResponse>('/memories/upsert', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function getRecentUploads(): Promise<RecentUpload[]> {
  const response = await request<RecentUploadsResponse>('/uploads/recent', {
    method: 'GET',
  });
  return response.items;
}

export async function getMemoryById(id: string): Promise<MemoryRecord> {
  return request<MemoryRecord>(`/debug/memories/${encodeURIComponent(id)}`, {
    method: 'GET',
  });
}

export async function getRheomodeRun(runId: string): Promise<RheomodeRun> {
  return request<RheomodeRun>(`/debug/rheomode/${encodeURIComponent(runId)}`, {
    method: 'GET',
  });
}

export async function getContradictions(
  params: ContradictionQueryParams = {},
): Promise<ContradictionRecord[]> {
  const query = buildQueryString(params);
  const response = await request<ContradictionsResponse>(`/debug/contradictions${query}`, {
    method: 'GET',
  });
  return response.items;
}

