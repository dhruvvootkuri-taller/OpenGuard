import { useCallback, useEffect, useRef, useState } from 'react';
import { analyzeFrame } from '../api/eventsApi';
import type { DetectionBox, MonitorFeed, SecurityEvent } from '../types';

interface Props {
  feed: MonitorFeed;
  /** Notifies the console that this feed produced a backend event. */
  onEvent: (event: SecurityEvent) => void;
}

/** How often we grab a frame from the playing clip and send it for analysis. */
const FRAME_INTERVAL_MS = 5000;
const CAPTURE_WIDTH = 640;
const JPEG_QUALITY = 0.7;

/**
 * Capture the current frame of a playing <video> as a base64 JPEG.
 * Returns the raw base64 payload (no `data:` prefix) the backend expects,
 * or null if the frame isn't ready yet.
 */
function captureFrame(video: HTMLVideoElement): string | null {
  if (!video.videoWidth || !video.videoHeight) return null;
  const scale = Math.min(1, CAPTURE_WIDTH / video.videoWidth);
  const width = Math.round(video.videoWidth * scale);
  const height = Math.round(video.videoHeight * scale);
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  ctx.drawImage(video, 0, 0, width, height);
  const dataUrl = canvas.toDataURL('image/jpeg', JPEG_QUALITY);
  const comma = dataUrl.indexOf(',');
  return comma === -1 ? null : dataUrl.slice(comma + 1);
}

export function VideoMonitor({ feed, onEvent }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [sourceUrl, setSourceUrl] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [clock, setClock] = useState(() => new Date());
  const [boxes, setBoxes] = useState<DetectionBox[]>([]);
  const [status, setStatus] = useState<string>('idle');
  const [lastError, setLastError] = useState<string | null>(null);
  const inFlight = useRef(false);

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

  const sendFrame = useCallback(async () => {
    const video = videoRef.current;
    if (!video || inFlight.current) return;
    const image = captureFrame(video);
    if (!image) return;
    inFlight.current = true;
    setStatus('analyzing');
    try {
      const result = await analyzeFrame(feed.id, {
        image_base64: image,
        media_type: 'image/jpeg',
        is_armed_zone: feed.armed,
        zone: feed.zone,
      });
      setLastError(null);
      if (result.is_emergency && result.event) {
        setBoxes(result.event.detections);
        setStatus(`⚠ ${result.label}`);
        onEvent(result.event);
      } else {
        setBoxes([]);
        setStatus('all clear');
      }
    } catch (err) {
      setLastError((err as Error).message);
      setStatus('error');
    } finally {
      inFlight.current = false;
    }
  }, [feed, onEvent]);

  // While the clip is playing, periodically capture + analyze a frame.
  useEffect(() => {
    if (!playing) return undefined;
    const t = setInterval(() => {
      void sendFrame();
    }, FRAME_INTERVAL_MS);
    return () => clearInterval(t);
  }, [playing, sendFrame]);

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    if (sourceUrl) URL.revokeObjectURL(sourceUrl);
    const url = URL.createObjectURL(file);
    setSourceUrl(url);
    setFileName(file.name);
    setBoxes([]);
    setLastError(null);
    setStatus('idle');
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
              crossOrigin="anonymous"
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
          {sourceUrl ? (playing ? `Streaming · ${status}` : 'Paused') : 'No signal'}
        </span>
        <div className="monitor__actions">
          {sourceUrl && (
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => void sendFrame()}
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
