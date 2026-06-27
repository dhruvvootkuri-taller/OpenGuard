export interface DetectionBox {
  label: string;
  confidence: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface SecurityEvent {
  id: string;
  camera_id: string;
  status: string;
  threat_severity: string;
  threat_confidence: number;
  description: string;
  detected_at: string;
  escalated: boolean;
  detections: DetectionBox[];
}

/** Terminal lifecycle statuses — these are off the live/active views. */
export const TERMINAL_STATUSES = ['resolved', 'dismissed'] as const;

/** True while an event still belongs in the live/active views. */
export function isActiveEvent(event: SecurityEvent): boolean {
  return !TERMINAL_STATUSES.includes(
    event.status.toLowerCase() as (typeof TERMINAL_STATUSES)[number],
  );
}

/** True once an event has been resolved or dismissed. */
export function isResolvedEvent(event: SecurityEvent): boolean {
  return event.status.toLowerCase() === 'resolved';
}

/** Payload accepted by POST /api/events. */
export interface ProcessDetectionRequest {
  camera_id: string;
  detections: DetectionBox[];
  is_armed_zone: boolean;
  description: string;
}

/** Payload accepted by POST /api/feeds/{camera_id}/frame. */
export interface AnalyzeFrameRequest {
  /** Raw base64-encoded JPEG bytes (no data: prefix). */
  image_base64: string;
  media_type: string;
  is_armed_zone: boolean;
  zone: string;
}

/** Response from POST /api/feeds/{camera_id}/frame. */
export interface AnalyzeFrameResponse {
  camera_id: string;
  is_emergency: boolean;
  label: string;
  summary: string;
  /** Populated only when an emergency was confirmed. */
  event: SecurityEvent | null;
}

/** A single monitor on the video wall. */
export interface MonitorFeed {
  /** Stable slot id, e.g. "CAM-01". */
  id: string;
  /** Human label for the zone the camera watches. */
  zone: string;
  /** Whether this zone is armed (raises threat scoring on the backend). */
  armed: boolean;
}
