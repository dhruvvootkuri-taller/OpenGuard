import { EventCard } from './EventCard';
import { Panel } from './Panel';
import type { SecurityEvent } from '../types';
import { isActiveEvent } from '../types';

interface Props {
  events: SecurityEvent[];
  onAcknowledge: (event: SecurityEvent) => void;
  onResolve: (event: SecurityEvent) => void;
  onDismiss: (event: SecurityEvent) => void;
}

/**
 * Live emergency / flag feed. Shows only active (unresolved, undismissed)
 * events, newest first, with acknowledge/resolve/dismiss actions for the
 * on-duty operator. Resolved and dismissed events fall off this panel.
 */
export function EmergencyLog({
  events,
  onAcknowledge,
  onResolve,
  onDismiss,
}: Props) {
  const active = events.filter(isActiveEvent);
  const flagged = active.filter(
    (e) => !['info', 'low'].includes(e.threat_severity.toLowerCase()),
  ).length;

  return (
    <Panel title="Emergency Log & Flags" count={flagged} accent="alert">
      {active.length === 0 ? (
        <p className="empty">No flags. Perimeter quiet.</p>
      ) : (
        <ul className="event-list">
          {active.map((event) => (
            <EventCard
              key={event.id}
              event={event}
              onAcknowledge={onAcknowledge}
              onResolve={onResolve}
              onDismiss={onDismiss}
            />
          ))}
        </ul>
      )}
    </Panel>
  );
}
