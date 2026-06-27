import type { SecurityEvent } from '../types';
import { isActiveEvent } from '../types';

interface Props {
  events: SecurityEvent[];
  online: boolean;
  clock: Date;
}

/** Top KPI strip for the operations console. Counts reflect current activity
 * (active, unresolved events) rather than the full historical pile. */
export function StatusBar({ events, online, clock }: Props) {
  const active = events.filter(isActiveEvent);
  const critical = active.filter(
    (e) => e.threat_severity.toLowerCase() === 'critical',
  ).length;
  const escalations = active.filter((e) => e.escalated).length;
  const acknowledged = active.filter(
    (e) => e.status.toLowerCase() === 'acknowledged',
  ).length;

  return (
    <div className="statusbar">
      <div className="statusbar__group">
        <Kpi label="Active Events" value={active.length} />
        <Kpi label="Critical" value={critical} tone="critical" />
        <Kpi label="Escalations" value={escalations} tone="high" />
        <Kpi label="Acknowledged" value={acknowledged} tone="ok" />
      </div>
      <div className="statusbar__sys">
        <span className={`statusbar__link ${online ? 'is-up' : 'is-down'}`}>
          <span className="statusbar__link-dot" />
          {online ? 'Backend Online' : 'Backend Offline'}
        </span>
        <span className="statusbar__clock">
          {clock.toLocaleString([], { hour12: false })}
        </span>
      </div>
    </div>
  );
}

function Kpi({
  label,
  value,
  tone = 'default',
}: {
  label: string;
  value: number;
  tone?: 'default' | 'critical' | 'high' | 'ok';
}) {
  return (
    <div className={`kpi kpi--${tone}`}>
      <span className="kpi__value">{value}</span>
      <span className="kpi__label">{label}</span>
    </div>
  );
}
