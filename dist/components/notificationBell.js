import { fetchScheduledNotifications } from '../utils/notificationApi.js';

export function initNotificationBell() {
  const btn = document.getElementById('open-notifications');
  const list = document.getElementById('notification-list');
  if (!btn || !list) return null;
  async function refresh() {
    try {
      const res = await fetchScheduledNotifications();
      const items = (res.data || []).slice(0, 8);
      const pending = (res.summary && res.summary.pending) || items.filter((item) => item.status === 'pending').length;
      btn.dataset.count = String(pending);
      btn.classList.toggle('has-notifications', pending > 0);
      if (!items.length) return;
      list.innerHTML = items.map((item) => `<div class="notification-item"><strong>${item.title || ''}</strong><span>${item.channel || ''} · ${item.status || ''}</span></div>`).join('');
    } catch {}
  }
  refresh();
  setInterval(refresh, 60000);
  return { refresh };
}
