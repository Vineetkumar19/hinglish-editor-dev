import { useEffect, useState } from 'react';
import { apiFetch } from './api';

export default function DocumentReminders({ enabled, onOpen }) {
  const [tasks, setTasks] = useState([]);
  useEffect(() => {
    if (!enabled) return;
    let closed = false, reading = false;
    async function refresh() {
      if (reading) return;
      reading = true;
      try {
        const response = await apiFetch('/api/local/tasks/due');
        if (response.ok) {
          const body = await response.json();
          if (!closed) setTasks(body.tasks);
        }
      } catch { /* Keep undismissed reminders; retry on reconnect or wake. */ }
      finally { reading = false; }
    }
    queueMicrotask(refresh);
    const timer = setInterval(refresh, 30000);
    window.addEventListener('focus', refresh);
    return () => { closed = true; clearInterval(timer); window.removeEventListener('focus', refresh); };
  }, [enabled]);
  if (!enabled || !tasks.length) return null;
  return <aside className="document-reminders" role="status">
    <strong>{tasks.length} document {tasks.length === 1 ? 'deadline needs' : 'deadlines need'} attention</strong>
    <span> {tasks.slice(0, 3).map(t => t.title).join(' · ')}</span>
    <button onClick={onOpen}>Review reminders</button>
  </aside>;
}
