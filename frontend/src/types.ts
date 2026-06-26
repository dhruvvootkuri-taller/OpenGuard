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

/** Payload accepted by POST /api/events. */
export interface ProcessDetectionRequest {
  camera_id: string;
  detections: DetectionBox[];
  is_armed_zone: boolean;
  description: string;
}

/** Payload accepted by POST /api/feeds/{camera_id}/frame. */
export interface AnalyzeFrameRequest {
  /** Raw base64 of the captured JPEG frame (no data: prefix). */
  image_base64: string;
  media_type: string;
  is_armed_zone: boolean;
  zone: string;
}

/** Response from POST /api/feeds/{camera_id}/frame. */
export interface AnalyzeFrameResult {
  camera_id: string;
  is_emergency: boolean;
  label: string;
  summary: string;
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
