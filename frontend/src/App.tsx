import { useEffect, useState } from 'react';
import { fetchRecentEvents } from './api/eventsApi';
import { EventCard } from './components/EventCard';
import type { SecurityEvent } from './types';

export default function App() {
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const load = async () => {
      try {
        const data = await fetchRecentEvents();
        if (active) {
          setEvents(data);
          setError(null);
        }
      } catch (err) {
        if (active) setError((err as Error).message);
      }
    };

    load();
    const interval = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="app">
      <header className="app__header">
        <h1 className="app__title">🛡️ Open Guard</h1>
        <span className="app__subtitle">Live security events</span>
      </header>

      {error && <p className="empty">⚠️ {error}</p>}

      {events.length === 0 && !error ? (
        <p className="empty">No events yet. The perimeter is quiet.</p>
      ) : (
        <ul className="event-list">
          {events.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </ul>
      )}
    </div>
  );
}
