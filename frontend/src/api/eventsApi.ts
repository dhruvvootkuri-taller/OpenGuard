import type {
  AnalyzeFrameRequest,
  AnalyzeFrameResponse,
  ProcessDetectionRequest,
  SecurityEvent,
} from '../types';

const BASE_URL = '/api/events';
const FEEDS_URL = '/api/feeds';

export async function fetchRecentEvents(limit = 50): Promise<SecurityEvent[]> {
  const res = await fetch(`${BASE_URL}?limit=${limit}`);
  if (!res.ok) {
    throw new Error(`Failed to load events: ${res.status}`);
  }
  return (await res.json()) as SecurityEvent[];
}

export async function acknowledgeEvent(
  eventId: string,
  operatorId: string,
): Promise<SecurityEvent> {
  const res = await fetch(`${BASE_URL}/${eventId}/acknowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId }),
  });
  if (!res.ok) {
    throw new Error(`Failed to acknowledge event: ${res.status}`);
  }
  return (await res.json()) as SecurityEvent;
}

/** Resolve an event — drops it from the active views (kept in Call History
 * if it was escalated, as an audit trail). */
export async function resolveEvent(eventId: string): Promise<SecurityEvent> {
  const res = await fetch(`${BASE_URL}/${eventId}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`Failed to resolve event: ${res.status}`);
  }
  return (await res.json()) as SecurityEvent;
}

/** Dismiss an event as a non-incident (false positive / noise). */
export async function dismissEvent(eventId: string): Promise<SecurityEvent> {
  const res = await fetch(`${BASE_URL}/${eventId}/dismiss`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`Failed to dismiss event: ${res.status}`);
  }
  return (await res.json()) as SecurityEvent;
}

/** Supported reset path. Clears resolved/dismissed events (or everything when
 * `includeActive` is set). Returns how many events were removed. */
export async function clearResolvedEvents(
  includeActive = false,
): Promise<number> {
  const res = await fetch(`${BASE_URL}/clear-resolved`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ include_active: includeActive }),
  });
  if (!res.ok) {
    throw new Error(`Failed to clear events: ${res.status}`);
  }
  const data = (await res.json()) as { cleared: number };
  return data.cleared;
}

/**
 * Submit a detection produced by a (simulated) live feed. Drives the real
 * Open Guard threat-assessment + escalation pipeline on the backend.
 */
export async function processDetection(
  payload: ProcessDetectionRequest,
): Promise<SecurityEvent> {
  const res = await fetch(BASE_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Failed to submit detection: ${res.status}`);
  }
  return (await res.json()) as SecurityEvent;
}

/**
 * Submit a single captured MP4 frame to the Claude-vision pipeline.
 * The backend assesses the frame and creates a SecurityEvent on a detected
 * emergency (returned as `event`); otherwise `event` is null.
 */
export async function analyzeFrame(
  cameraId: string,
  payload: AnalyzeFrameRequest,
): Promise<AnalyzeFrameResponse> {
  const res = await fetch(`${FEEDS_URL}/${encodeURIComponent(cameraId)}/frame`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Failed to analyze frame: ${res.status}`);
  }
  return (await res.json()) as AnalyzeFrameResponse;
}
