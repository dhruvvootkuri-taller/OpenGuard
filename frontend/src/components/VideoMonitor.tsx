import { useCallback, useEffect, useRef, useState } from 'react';
import { analyzeFrame } from '../api/eventsApi';
import type { DetectionBox, MonitorFeed, SecurityEvent } from '../types';

interface Props {
  feed: MonitorFeed;
  /** Notifies the console that this feed produced a backend event. */
  onEvent: (event: SecurityEvent) => void;
}

/** How often (ms) a frame is grabbed from the playing clip and analysed. */
const FRAME_INTERVAL_MS = 4000;
/** Downscaled capture width (px) — keeps payloads small for real-time use. */
const CAPTURE_WIDTH = 640;

/**
 * Grab the current frame from a <video> element and return it as raw base64
 * JPEG (no data: prefix), ready for POST /api/feeds/{id}/frame. Returns null
 * if the frame is not yet decodable.
 */
function captureFrame(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
): string | null {
  if (!video.videoWidth || !video.videoHeight) return null;
  const scale = Math.min(1, CAPTURE_WIDTH / video.videoWidth);
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
  const comma = dataUrl.indexOf(',');
  return comma >= 0 ? dataUrl.slice(comma + 1) : null;
}

export function VideoMonitor({ feed, onEvent }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
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

  // Grab the current frame and send it to Anthropic-backed analysis. An event
  // (and its bounding box) is only produced when the model reports a real
  // emergency; otherwise the feed clears its overlay and carries on.
  const analyzeCurrentFrame = useCallback(async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    const image = captureFrame(video, canvas);
    if (!image) return;
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
        onEvent(result.event);
      } else {
        setBoxes([]);
      }
    } catch (err) {
      setLastError((err as Error).message);
    }
  }, [feed, onEvent]);

  // While the clip is playing, grab and analyse frames in real time. Each
  // frame is processed as it is captured — playback is never blocked.
  useEffect(() => {
    if (!playing) return undefined;
    const t = setInterval(() => {
      void analyzeCurrentFrame();
    }, FRAME_INTERVAL_MS);
    return () => clearInterval(t);
  }, [playing, analyzeCurrentFrame]);

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
            <canvas ref={canvasRef} className="monitor__capture" hidden />
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
              onClick={() => void analyzeCurrentFrame()}
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
