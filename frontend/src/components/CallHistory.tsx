import { Panel } from './Panel';
import type { EscalationOutcome, SecurityEvent } from '../types';

interface Props {
  events: SecurityEvent[];
}

/** Human label + class suffix for an escalation outcome badge. */
const OUTCOME_META: Record<
  EscalationOutcome,
  { label: string; mod: string; icon: string }
> = {
  reached: { label: 'Reached', mod: 'reached', icon: '✓' },
  unreachable: { label: 'Unreachable', mod: 'unreachable', icon: '✕' },
  pending: { label: 'Pending', mod: 'pending', icon: '…' },
};

function outcomeMeta(event: SecurityEvent) {
  const outcome: EscalationOutcome = event.escalation_outcome ?? 'pending';
  return OUTCOME_META[outcome] ?? OUTCOME_META.pending;
}

/**
 * Audit trail of escalated calls that are no longer ongoing — acknowledged or
 * resolved (including auto-expired) escalations. Dismissed events are treated
 * as non-incidents and excluded.
 */
export function CallHistory({ events }: Props) {
  const history = events.filter((e) => {
    if (!e.escalated) return false;
    const status = e.status.toLowerCase();
    return status === 'acknowledged' || status === 'resolved';
  });

  return (
    <Panel title="Call History" count={history.length}>
      {history.length === 0 ? (
        <p className="empty">No resolved calls this shift.</p>
      ) : (
        <ul className="history-list">
          {history.map((event) => {
            const meta = outcomeMeta(event);
            return (
              <li key={event.id} className="history-item">
                <span
                  className={`history-item__check history-item__check--${meta.mod}`}
                  aria-hidden
                >
                  {meta.icon}
                </span>
                <span className="history-item__cam">{event.camera_id}</span>
                <span className="history-item__sev">
                  {event.threat_severity}
                </span>
                <span
                  className={`history-item__outcome history-item__outcome--${meta.mod}`}
                  title={
                    event.escalation_reached_contact
                      ? `Reached ${event.escalation_reached_contact}`
                      : event.escalation_attempts
                        ? `${event.escalation_attempts} contact(s) attempted`
                        : undefined
                  }
                >
                  {meta.label}
                </span>
                <span className="history-item__time">
                  {new Date(event.detected_at).toLocaleString([], {
                    hour12: false,
                  })}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}
