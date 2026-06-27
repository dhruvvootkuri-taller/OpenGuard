import { Panel } from './Panel';
import type { SecurityEvent } from '../types';
import { isActiveEvent } from '../types';

interface Props {
  events: SecurityEvent[];
}

/**
 * Genuinely active dispatch calls: escalated incidents that are still active
 * (not resolved/dismissed/expired) and not yet acknowledged by an operator.
 * Resolved or expired escalations drop off here and live on only in Call
 * History.
 */
export function OngoingCalls({ events }: Props) {
  const ongoing = events.filter(
    (e) =>
      e.escalated &&
      isActiveEvent(e) &&
      e.status.toLowerCase() !== 'acknowledged',
  );

  return (
    <Panel title="Ongoing Calls" count={ongoing.length} accent="live">
      {ongoing.length === 0 ? (
        <p className="empty">No active dispatch calls.</p>
      ) : (
        <ul className="call-list">
          {ongoing.map((event) => (
            <li key={event.id} className="call-item">
              <span className="call-item__pulse" aria-hidden />
              <div className="call-item__body">
                <strong>{event.camera_id}</strong>
                <span className="call-item__sev">{event.threat_severity}</span>
                <p className="call-item__desc">
                  {event.description || 'Dispatch in progress…'}
                </p>
              </div>
              <span className="call-item__since">
                {new Date(event.detected_at).toLocaleTimeString([], {
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
