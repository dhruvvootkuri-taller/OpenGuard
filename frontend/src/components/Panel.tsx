import type { ReactNode } from 'react';

interface Props {
  title: string;
  count?: number;
  accent?: 'default' | 'alert' | 'live';
  children: ReactNode;
}

/** Shared chrome for every side/bottom panel in the ops console. */
export function Panel({ title, count, accent = 'default', children }: Props) {
  return (
    <section className={`panel panel--${accent}`}>
      <header className="panel__header">
        <h2 className="panel__title">{title}</h2>
        {count !== undefined && <span className="panel__count">{count}</span>}
      </header>
      <div className="panel__body">{children}</div>
    </section>
  );
}
