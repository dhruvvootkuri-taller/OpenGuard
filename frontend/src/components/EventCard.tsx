import type { SecurityEvent } from '../types';
import { isResolvedEvent } from '../types';

interface Props {
  event: SecurityEvent;
  onAcknowledge?: (event: SecurityEvent) => void;
  onResolve?: (event: SecurityEvent) => void;
  onDismiss?: (event: SecurityEvent) => void;
}

export function EventCard({
  event,
  onAcknowledge,
  onResolve,
  onDismiss,
}: Props) {
  const severity = event.threat_severity.toLowerCase();
  const status = event.status.toLowerCase();
  const acknowledged = status === 'acknowledged';
  const terminal = status === 'resolved' || status === 'dismissed';
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
      {!terminal && (
        <div className="event-card__actions">
          {onAcknowledge && !acknowledged && (
            <button
              type="button"
              className="btn btn--ack"
              onClick={() => onAcknowledge(event)}
            >
              Acknowledge
            </button>
          )}
          {onResolve && (
            <button
              type="button"
              className="btn btn--resolve"
              onClick={() => onResolve(event)}
            >
              Resolve
            </button>
          )}
          {onDismiss && (
            <button
              type="button"
              className="btn btn--dismiss"
              onClick={() => onDismiss(event)}
            >
              Dismiss
            </button>
          )}
        </div>
      )}
      {terminal && (
        <div className="event-card__meta">
          <span>{isResolvedEvent(event) ? 'Resolved' : 'Dismissed'}</span>
        </div>
      )}
    </li>
  );
}
