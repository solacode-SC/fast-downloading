export type Platform = "youtube" | "x" | "instagram" | "facebook";

export type Preset =
  | "best"
  | "compatible"
  | "2160p"
  | "1440p"
  | "1080p"
  | "720p"
  | "480p"
  | "audio_m4a"
  | "audio_mp3_320"
  | "audio_mp3_192";

export type JobStatus =
  "queued" | "resolving" | "downloading" | "merging" | "ready" | "failed" | "cancelled";

export interface ErrorDetail {
  code: string;
  message: string;
  hint: string;
  retryable: boolean;
}

export interface SubtitleTrack {
  lang: string;
  name: string;
  ext: string;
  auto: boolean;
}

export interface FormatItem {
  format_id: string;
  ext: string;
  resolution: string | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  vcodec: string | null;
  acodec: string | null;
  is_hdr: boolean;
  is_audio_only: boolean;
  is_video_only: boolean;
  is_progressive: boolean;
  tbr_kbps: number | null;
  abr_kbps: number | null;
  filesize_bytes: number | null;
  filesize_approx_bytes: number | null;
  note: string | null;
  compatible: boolean;
}

export interface PresetOption {
  id: Preset;
  label: string;
  description: string;
  estimated_ext: string;
  estimated_height: number | null;
  estimated_size_bytes: number | null;
  available: boolean;
}

export interface MediaEntrySummary {
  index: number;
  id: string;
  title: string;
  url: string;
  duration_seconds: number | null;
  thumbnail_url: string | null;
}

export interface ResolveResponse {
  url: string;
  normalized_url: string;
  platform: Platform;
  id: string;
  title: string;
  uploader: string | null;
  duration_seconds: number | null;
  thumbnail_url: string | null;
  is_playlist: boolean;
  is_carousel: boolean;
  entries: MediaEntrySummary[];
  presets: PresetOption[];
  formats: FormatItem[];
  subtitles: SubtitleTrack[];
  cached: boolean;
  resolve_ms: number;
}

export interface CreateJobPayload {
  url: string;
  preset?: Preset;
  format_id?: string | null;
  audio_format?: "m4a" | "mp3_192" | "mp3_320" | null;
  subtitle_lang?: string | null;
  download_thumbnail?: boolean;
  playlist_item?: number | null;
  turnstile_token?: string | null;
}

export interface CreateJobResponse {
  job_id: string;
  status: JobStatus;
  reused: boolean;
}

export interface JobSnapshot {
  job_id: string;
  platform: Platform;
  url: string;
  title: string | null;
  thumbnail_url: string | null;
  status: JobStatus;
  progress_percent: number;
  downloaded_bytes: number;
  total_bytes: number | null;
  speed_bytes_per_sec: number | null;
  eta_seconds: number | null;
  phase_detail: string | null;
  download_token: string | null;
  download_url: string | null;
  filename: string | null;
  mime_type: string | null;
  filesize_bytes: number | null;
  subtitle_token: string | null;
  subtitle_url: string | null;
  thumbnail_token: string | null;
  thumbnail_url_download: string | null;
  error: ErrorDetail | null;
  created_at: number;
  updated_at: number;
  expires_at: number | null;
}

export class ApiClientError extends Error {
  detail: ErrorDetail;
  status: number;

  constructor(detail: ErrorDetail, status: number) {
    super(detail.message);
    this.detail = detail;
    this.status = status;
  }
}

async function parseResponse<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail: ErrorDetail = data?.error || {
      code: "HTTP_ERROR",
      message: `Request failed with status ${res.status}`,
      hint: "Please try again shortly.",
      retryable: res.status >= 500 || res.status === 429,
    };
    throw new ApiClientError(detail, res.status);
  }
  return data as T;
}

export async function resolveUrl(url: string, signal?: AbortSignal): Promise<ResolveResponse> {
  const res = await fetch("/api/v1/resolve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
    signal,
  });
  return parseResponse<ResolveResponse>(res);
}

export async function createDownloadJob(payload: CreateJobPayload): Promise<CreateJobResponse> {
  const res = await fetch("/api/v1/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse<CreateJobResponse>(res);
}

export async function fetchJobSnapshot(jobId: string): Promise<JobSnapshot> {
  const res = await fetch(`/api/v1/jobs/${encodeURIComponent(jobId)}`, {
    cache: "no-store",
  });
  return parseResponse<JobSnapshot>(res);
}

export async function cancelDownloadJob(jobId: string): Promise<void> {
  const res = await fetch(`/api/v1/jobs/${encodeURIComponent(jobId)}`, {
    method: "DELETE",
  });
  await parseResponse<unknown>(res);
}

export function subscribeJobEvents(
  jobId: string,
  onSnapshot: (snap: JobSnapshot) => void,
  onConnectionError: () => void
): () => void {
  let closed = false;
  let es: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let attempts = 0;

  const terminal = new Set<JobStatus>(["ready", "failed", "cancelled"]);

  const connect = () => {
    if (closed) return;
    es = new EventSource(`/api/v1/jobs/${encodeURIComponent(jobId)}/events`);

    es.addEventListener("progress", (evt: MessageEvent) => {
      attempts = 0;
      try {
        const snap = JSON.parse(evt.data) as JobSnapshot;
        onSnapshot(snap);
        if (terminal.has(snap.status)) {
          cleanup();
        }
      } catch {
        // Ignore malformed frame
      }
    });

    es.onerror = () => {
      es?.close();
      es = null;
      if (closed) return;
      attempts += 1;
      if (attempts > 6) {
        onConnectionError();
        return;
      }
      const delay = Math.min(5000, 500 * Math.pow(1.6, attempts));
      reconnectTimer = setTimeout(connect, delay);
    };
  };

  const cleanup = () => {
    closed = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (es) {
      es.close();
      es = null;
    }
  };

  connect();
  return cleanup;
}
