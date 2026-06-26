import { Panel } from './Panel';
import type { SecurityEvent } from '../types';

interface Props {
  events: SecurityEvent[];
}

/**
 * Resolved escalations — calls that have been acknowledged by an operator.
 * Acts as an audit trail for the shift.
 */
export function CallHistory({ events }: Props) {
  const history = events.filter(
    (e) => e.escalated && e.status.toLowerCase() === 'acknowledged',
  );

  return (
    <Panel title="Call History" count={history.length}>
      {history.length === 0 ? (
        <p className="empty">No resolved calls this shift.</p>
      ) : (
        <ul className="history-list">
          {history.map((event) => (
            <li key={event.id} className="history-item">
              <span className="history-item__check" aria-hidden>
                ✓
              </span>
              <span className="history-item__cam">{event.camera_id}</span>
              <span className="history-item__sev">{event.threat_severity}</span>
              <span className="history-item__time">
                {new Date(event.detected_at).toLocaleString([], {
                  hour12: false,
                })}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
