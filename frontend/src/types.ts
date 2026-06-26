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
