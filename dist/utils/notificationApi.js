export async function fetchNotificationPreferences() {
  const res = await fetch('/api/notifications/preferences');
  if (!res.ok) throw new Error('Bildirim tercihleri alınamadı.');
  return res.json();
}

export async function saveNotificationPreferences(preferences) {
  const res = await fetch('/api/notifications/preferences', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(preferences)
  });
  if (!res.ok) throw new Error('Bildirim tercihleri kaydedilemedi.');
  return res.json();
}

export async function subscribePush(subscription) {
  const res = await fetch('/api/notifications/push/subscribe', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(subscription)
  });
  if (!res.ok) throw new Error('Push aboneliği kaydedilemedi.');
  return res.json();
}

export async function unsubscribePush(endpoint = '') {
  const res = await fetch('/api/notifications/push/unsubscribe', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ endpoint })
  });
  if (!res.ok) throw new Error('Push aboneliği kapatılamadı.');
  return res.json();
}

export async function sendTestNotification(channel = '') {
  const res = await fetch('/api/notifications/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(channel ? { channel } : {})
  });
  if (!res.ok) throw new Error('Test bildirimi gönderilemedi.');
  return res.json();
}

export async function fetchScheduledNotifications(status = '') {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  const res = await fetch(`/api/notifications/scheduled${qs}`);
  if (!res.ok) throw new Error('Planlanmış bildirimler alınamadı.');
  return res.json();
}
