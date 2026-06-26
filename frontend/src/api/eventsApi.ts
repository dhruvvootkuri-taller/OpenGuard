import type {
  AnalyzeFrameRequest,
  AnalyzeFrameResult,
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
 * Send a single frame captured from a playing MP4 feed to Anthropic-backed
 * emergency analysis. Frames are analysed in real time as they are captured;
 * an emergency is recorded only when the model reports one (event !== null).
 */
export async function analyzeFrame(
  cameraId: string,
  payload: AnalyzeFrameRequest,
): Promise<AnalyzeFrameResult> {
  const res = await fetch(`${FEEDS_URL}/${cameraId}/frame`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Failed to analyze frame: ${res.status}`);
  }
  return (await res.json()) as AnalyzeFrameResult;
}
