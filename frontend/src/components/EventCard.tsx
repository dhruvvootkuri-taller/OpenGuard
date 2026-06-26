import type { SecurityEvent } from '../types';

interface Props {
  event: SecurityEvent;
  onAcknowledge?: (event: SecurityEvent) => void;
}

export function EventCard({ event, onAcknowledge }: Props) {
  const severity = event.threat_severity.toLowerCase();
  const acknowledged = event.status.toLowerCase() === 'acknowledged';
  return (
    <li className={`event-card event-card--${severity}`}>
      <div className="event-card__top">
        <strong>{event.camera_id}</strong>
        <span className={`badge badge--${severity}`}>
          {event.threat_severity}
          {event.escalated ? ' • ESC' : ''}
        </span>
      </div>
      <p className="event-card__desc">{event.description || 'No description'}</p>
      <div className="event-card__meta">
        <span>{event.status}</span>
        <span>{(event.threat_confidence * 100).toFixed(0)}%</span>
        <span>{new Date(event.detected_at).toLocaleTimeString([], { hour12: false })}</span>
      </div>
      {onAcknowledge && !acknowledged && (
        <button
          type="button"
          className="btn btn--ack"
          onClick={() => onAcknowledge(event)}
        >
          Acknowledge
        </button>
      )}
    </li>
  );
}
