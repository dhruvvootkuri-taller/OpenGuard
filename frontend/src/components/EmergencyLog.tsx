import { EventCard } from './EventCard';
import { Panel } from './Panel';
import type { SecurityEvent } from '../types';

interface Props {
  events: SecurityEvent[];
  onAcknowledge: (event: SecurityEvent) => void;
}

/**
 * Live emergency / flag feed. Shows every assessed event, newest first, with
 * an acknowledge action for the on-duty operator.
 */
export function EmergencyLog({ events, onAcknowledge }: Props) {
  const flagged = events.filter(
    (e) => !['info', 'low'].includes(e.threat_severity.toLowerCase()),
  ).length;

  return (
    <Panel title="Emergency Log & Flags" count={flagged} accent="alert">
      {events.length === 0 ? (
        <p className="empty">No flags. Perimeter quiet.</p>
      ) : (
        <ul className="event-list">
          {events.map((event) => (
            <EventCard
              key={event.id}
              event={event}
              onAcknowledge={onAcknowledge}
            />
          ))}
        </ul>
      )}
    </Panel>
  );
}
