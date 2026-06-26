import { useCallback, useEffect, useRef, useState } from 'react';
import { processDetection } from '../api/eventsApi';
import type { DetectionBox, MonitorFeed, SecurityEvent } from '../types';

interface Props {
  feed: MonitorFeed;
  /** Notifies the console that this feed produced a backend event. */
  onEvent: (event: SecurityEvent) => void;
}

/**
 * Catalogue of objects the (mock) vision model can "detect" while a clip
 * plays. The backend assesses each one; armed zones + dangerous labels are
 * what trigger high/critical escalations.
 */
const DETECTION_LABELS: ReadonlyArray<{ label: string; weight: number }> = [
  { label: 'person', weight: 5 },
  { label: 'vehicle', weight: 3 },
  { label: 'backpack', weight: 2 },
  { label: 'knife', weight: 1 },
  { label: 'firearm', weight: 1 },
  { label: 'crowd', weight: 1 },
];

function pickLabel(): string {
  const pool: string[] = [];
  for (const { label, weight } of DETECTION_LABELS) {
    for (let i = 0; i < weight; i += 1) pool.push(label);
  }
  return pool[Math.floor(Math.random() * pool.length)];
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Build a randomized but schema-valid detection box (normalized 0..1). */
function randomDetection(): DetectionBox {
  const width = clamp(0.1 + Math.random() * 0.25, 0.05, 0.6);
  const height = clamp(0.15 + Math.random() * 0.3, 0.05, 0.7);
  const x = clamp(Math.random() * (1 - width), 0, 1 - width);
  const y = clamp(Math.random() * (1 - height), 0, 1 - height);
  return {
    label: pickLabel(),
    confidence: clamp(0.55 + Math.random() * 0.44, 0, 1),
    x,
    y,
    width,
    height,
  };
}

const DETECTION_INTERVAL_MS = 7000;

export function VideoMonitor({ feed, onEvent }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [sourceUrl, setSourceUrl] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [clock, setClock] = useState(() => new Date());
  const [boxes, setBoxes] = useState<DetectionBox[]>([]);
  const [lastError, setLastError] = useState<string | null>(null);

  // Revoke object URLs to avoid leaks when the source changes / unmounts.
  useEffect(() => {
    return () => {
      if (sourceUrl) URL.revokeObjectURL(sourceUrl);
    };
  }, [sourceUrl]);

  // Overlay clock ticks every second while there is a source.
  useEffect(() => {
    if (!sourceUrl) return undefined;
    const t = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(t);
  }, [sourceUrl]);

  const emitDetection = useCallback(async () => {
    const detections = [randomDetection()];
    setBoxes(detections);
    try {
      const event = await processDetection({
        camera_id: feed.id,
        detections,
        is_armed_zone: feed.armed,
        description: `Auto-detection on ${feed.id} (${feed.zone})`,
      });
      setLastError(null);
      onEvent(event);
    } catch (err) {
      setLastError((err as Error).message);
    }
  }, [feed, onEvent]);

  // While the clip is playing, periodically push detections to the backend.
  useEffect(() => {
    if (!playing) return undefined;
    const t = setInterval(() => {
      void emitDetection();
    }, DETECTION_INTERVAL_MS);
    return () => clearInterval(t);
  }, [playing, emitDetection]);

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    if (sourceUrl) URL.revokeObjectURL(sourceUrl);
    const url = URL.createObjectURL(file);
    setSourceUrl(url);
    setFileName(file.name);
    setBoxes([]);
    setLastError(null);
  };

  return (
    <div className={`monitor ${playing ? 'monitor--live' : ''}`}>
      <div className="monitor__bezel">
        {sourceUrl ? (
          <>
            <video
              ref={videoRef}
              className="monitor__video"
              src={sourceUrl}
              loop
              muted
              playsInline
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onEnded={() => setPlaying(false)}
            />
            <div className="monitor__scanline" aria-hidden />
            {boxes.map((box, i) => (
              <div
                key={i}
                className="monitor__box"
                style={{
                  left: `${box.x * 100}%`,
                  top: `${box.y * 100}%`,
                  width: `${box.width * 100}%`,
                  height: `${box.height * 100}%`,
                }}
              >
                <span className="monitor__box-label">
                  {box.label} {(box.confidence * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </>
        ) : (
          <label className="monitor__dropzone">
            <span className="monitor__dropzone-icon">⬆</span>
            <span className="monitor__dropzone-text">
              Load MP4 feed for {feed.id}
            </span>
            <input
              type="file"
              accept="video/mp4,video/*"
              className="monitor__input"
              onChange={(e) => handleFile(e.target.files?.[0])}
            />
          </label>
        )}

        {/* Live HUD overlay */}
        <div className="monitor__hud monitor__hud--top">
          <span className="monitor__cam">{feed.id}</span>
          {playing && (
            <span className="monitor__rec">
              <span className="monitor__rec-dot" /> REC
            </span>
          )}
        </div>
        <div className="monitor__hud monitor__hud--bottom">
          <span className="monitor__zone">
            {feed.zone}
            {feed.armed ? ' • ARMED' : ''}
          </span>
          <span className="monitor__time">
            {clock.toLocaleTimeString([], { hour12: false })}
          </span>
        </div>
      </div>

      <div className="monitor__controls">
        <span className="monitor__status">
          {sourceUrl
            ? playing
              ? 'Streaming · analyzing'
              : 'Paused'
            : 'No signal'}
        </span>
        <div className="monitor__actions">
          {sourceUrl && (
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => void emitDetection()}
            >
              Scan now
            </button>
          )}
          <label className="btn btn--ghost">
            {sourceUrl ? 'Swap clip' : 'Upload'}
            <input
              type="file"
              accept="video/mp4,video/*"
              className="monitor__input"
              onChange={(e) => handleFile(e.target.files?.[0])}
            />
          </label>
        </div>
      </div>
      {fileName && <span className="monitor__filename">{fileName}</span>}
      {lastError && <span className="monitor__error">⚠ {lastError}</span>}
    </div>
  );
}
