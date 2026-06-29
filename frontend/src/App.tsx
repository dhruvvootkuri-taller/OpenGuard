import { useCallback, useEffect, useState } from 'react';
import {
  acknowledgeEvent,
  clearResolvedEvents,
  dismissEvent,
  fetchCameras,
  fetchRecentEvents,
  resolveEvent,
} from './api/eventsApi';
import { CallHistory } from './components/CallHistory';
import { EmergencyLog } from './components/EmergencyLog';
import { OngoingCalls } from './components/OngoingCalls';
import { StatusBar } from './components/StatusBar';
import { VideoMonitor } from './components/VideoMonitor';
import type { MonitorFeed, SecurityEvent } from './types';

const OPERATOR_ID = 'operator-console';

function mergeEvent(prev: SecurityEvent[], next: SecurityEvent): SecurityEvent[] {
  const without = prev.filter((e) => e.id !== next.id);
  return [next, ...without].slice(0, 100);
}

export default function App() {
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [feeds, setFeeds] = useState<MonitorFeed[]>([]);
  const [online, setOnline] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clock, setClock] = useState(() => new Date());

  // Load the operator-configured camera feeds. There are no baked-in demo
  // cameras: with none configured the wall renders its empty state.
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const cameras = await fetchCameras();
        if (active) setFeeds(cameras);
      } catch (err) {
        if (active) setError((err as Error).message);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  // Poll the backend for the authoritative event list.
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const data = await fetchRecentEvents();
        if (!active) return;
        setEvents(data);
        setOnline(true);
        setError(null);
      } catch (err) {
        if (!active) return;
        setOnline(false);
        setError((err as Error).message);
      }
    };
    void load();
    const interval = setInterval(() => void load(), 5000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  // Console clock.
  useEffect(() => {
    const t = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // Optimistic merge when a monitor emits an event so the wall feels live
  // before the next poll cycle.
  const handleMonitorEvent = useCallback((event: SecurityEvent) => {
    setEvents((prev) => mergeEvent(prev, event));
    setOnline(true);
  }, []);

  const handleAcknowledge = useCallback(async (event: SecurityEvent) => {
    try {
      const updated = await acknowledgeEvent(event.id, OPERATOR_ID);
      setEvents((prev) => mergeEvent(prev, updated));
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  const handleResolve = useCallback(async (event: SecurityEvent) => {
    try {
      const updated = await resolveEvent(event.id);
      setEvents((prev) => mergeEvent(prev, updated));
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  const handleDismiss = useCallback(async (event: SecurityEvent) => {
    try {
      const updated = await dismissEvent(event.id);
      setEvents((prev) => mergeEvent(prev, updated));
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  const handleClearResolved = useCallback(async () => {
    try {
      await clearResolvedEvents(false);
      // Drop terminal events locally; the next poll reconciles the rest.
      setEvents((prev) =>
        prev.filter(
          (e) => !['resolved', 'dismissed'].includes(e.status.toLowerCase()),
        ),
      );
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  return (
    <div className="console">
      <header className="console__header">
        <div className="console__brand">
          <span className="console__logo">🛡️</span>
          <div>
            <h1 className="console__title">OPEN GUARD</h1>
            <span className="console__subtitle">
              National Security Operations Center · Live Monitoring
            </span>
          </div>
        </div>
        <StatusBar events={events} online={online} clock={clock} />
        <button
          type="button"
          className="btn btn--clear"
          onClick={() => void handleClearResolved()}
          title="Remove resolved & dismissed events"
        >
          Clear Resolved
        </button>
      </header>

      {error && <p className="console__error">⚠️ {error}</p>}

      <div className="console__grid">
        <main className="console__wall">
          {feeds.length > 0 ? (
            <div className="wall">
              {feeds.map((feed) => (
                <VideoMonitor
                  key={feed.id}
                  feed={feed}
                  onEvent={handleMonitorEvent}
                />
              ))}
            </div>
          ) : (
            <div className="wall wall--empty">
              <p className="empty">No cameras configured</p>
            </div>
          )}
          <CallHistory events={events} />
        </main>

        <aside className="console__side">
          <OngoingCalls events={events} />
          <EmergencyLog
            events={events}
            onAcknowledge={handleAcknowledge}
            onResolve={handleResolve}
            onDismiss={handleDismiss}
          />
        </aside>
      </div>
    </div>
  );
}
