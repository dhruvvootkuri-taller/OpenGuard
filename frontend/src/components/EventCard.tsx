import type { SecurityEvent } from '../types';

interface Props {
  event: SecurityEvent;
}

export function EventCard({ event }: Props) {
  const severity = event.threat_severity.toLowerCase();
  return (
    <li className="event-card">
      <div className="event-card__top">
        <strong>Camera {event.camera_id}</strong>
        <span className={`badge badge--${severity}`}>
          {event.threat_severity}
          {event.escalated ? ' • escalated' : ''}
        </span>
      </div>
      <p className="event-card__desc">{event.description || 'No description'}</p>
      <div className="event-card__meta">
        Status: {event.status} ·{' '}
        Confidence: {(event.threat_confidence * 100).toFixed(0)}% ·{' '}
        {new Date(event.detected_at).toLocaleString()}
      </div>
    </li>
  );
}
