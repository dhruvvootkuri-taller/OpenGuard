import type { ProcessDetectionRequest, SecurityEvent } from '../types';

const BASE_URL = '/api/events';

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
