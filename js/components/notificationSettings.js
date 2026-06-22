import {
  fetchNotificationPreferences,
  saveNotificationPreferences,
  sendTestNotification,
  fetchScheduledNotifications
} from '../utils/notificationApi.js';
import { browserSupportsPush, enablePushNotifications } from '../utils/pushNotifications.js';

const FIELD_MAP = [
  ['push_enabled', 'Push bildirimleri'],
  ['email_enabled', 'E-posta bildirimleri'],
  ['critical_announcements_enabled', 'Kritik duyurular'],
  ['event_reminders_enabled', 'Etkinlik hatırlatmaları'],
  ['one_day_before_enabled', '1 gün önce hatırlatma'],
  ['one_hour_before_enabled', '1 saat önce hatırlatma'],
  ['event_start_enabled', 'Etkinlik anında hatırlatma']
];

function escapeHtml(value = '') {
  return String(value ?? '').replace(/[&<>'"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[ch]));
}

export function initNotificationSettingsPanel(options = {}) {
  const root = document.getElementById('notification-settings-root');
  if (!root) return null;
  const toast = typeof options.showToast === 'function' ? options.showToast : () => {};
  let state = { preferences: null, vapidPublicKey: '', scheduled: [] };

  function renderStatus(message = '', type = 'info') {
    const target = root.querySelector('[data-notification-status]');
    if (target) {
      target.textContent = message;
      target.dataset.type = type;
    }
  }

  function render() {
    const pref = state.preferences || {};
    root.innerHTML = `
      <section class="notification-settings-panel">
        <div class="notification-settings-head">
          <div>
            <p class="kicker">Bildirim Merkezi</p>
            <h2>Kritik duyuru ve etkinlik bildirimleri</h2>
            <p>Push ve e-posta kanallarını yönet; etkinliklerden 1 gün veya 1 saat önce otomatik hatırlatma al.</p>
          </div>
          <button type="button" class="notification-permission-btn" data-enable-push>
            <i class="fa-solid fa-bell"></i> Bildirim izni ver
          </button>
        </div>
        <div class="notification-support-note ${browserSupportsPush() ? 'ok' : 'warn'}">
          ${browserSupportsPush() ? 'Tarayıcınız Web Push destekliyor.' : 'Tarayıcınız Web Push desteklemiyor; e-posta bildirimleri kullanılabilir.'}
        </div>
        <div class="notification-toggle-grid">
          ${FIELD_MAP.map(([field, label]) => `
            <label class="notification-toggle-card">
              <input type="checkbox" data-pref-field="${field}" ${pref[field] ? 'checked' : ''} />
              <span>${escapeHtml(label)}</span>
            </label>
          `).join('')}
        </div>
        <label class="notification-timezone-field">Saat dilimi
          <input type="text" data-pref-field="timezone" value="${escapeHtml(pref.timezone || 'Europe/Istanbul')}" />
        </label>
        <div class="notification-settings-actions">
          <button type="button" data-save-notification-preferences>Ayarları kaydet</button>
          <button type="button" data-send-test-notification>Test bildirimi gönder</button>
          <button type="button" data-refresh-scheduled>Planlananları yenile</button>
          <span data-notification-status aria-live="polite"></span>
        </div>
        <div class="notification-scheduled-list">
          <h3>Son planlanan bildirimler</h3>
          ${state.scheduled.length ? state.scheduled.slice(0, 8).map((item) => `
            <article class="notification-scheduled-item ${escapeHtml(item.status)}">
              <strong>${escapeHtml(item.title)}</strong>
              <span>${escapeHtml(item.channel)} · ${escapeHtml(item.notification_type)} · ${escapeHtml(item.status)}</span>
              <small>${escapeHtml(item.scheduled_at || '')}</small>
            </article>
          `).join('') : '<p class="notification-empty">Henüz planlanmış bildirim yok.</p>'}
        </div>
      </section>`;
    bindEvents();
  }

  function collectPreferences() {
    const payload = {};
    root.querySelectorAll('[data-pref-field]').forEach((field) => {
      const name = field.dataset.prefField;
      payload[name] = field.type === 'checkbox' ? field.checked : field.value;
    });
    return payload;
  }

  async function load() {
    root.innerHTML = '<div class="notification-loading">Bildirim ayarları yükleniyor...</div>';
    try {
      const prefRes = await fetchNotificationPreferences();
      const scheduledRes = await fetchScheduledNotifications();
      state.preferences = prefRes.data || {};
      state.vapidPublicKey = prefRes.vapidPublicKey || '';
      state.scheduled = scheduledRes.data || [];
      render();
    } catch (error) {
      root.innerHTML = `<div class="notification-error">${escapeHtml(error.message || 'Bildirim ekranı yüklenemedi.')}</div>`;
    }
  }

  function bindEvents() {
    root.querySelector('[data-save-notification-preferences]')?.addEventListener('click', async () => {
      renderStatus('Kaydediliyor...', 'loading');
      try {
        const res = await saveNotificationPreferences(collectPreferences());
        state.preferences = res.data || collectPreferences();
        renderStatus('Ayarlar kaydedildi.', 'success');
        toast('Bildirim ayarları kaydedildi.', 'success');
      } catch (error) {
        renderStatus(error.message || 'Kayıt başarısız.', 'error');
      }
    });
    root.querySelector('[data-enable-push]')?.addEventListener('click', async () => {
      renderStatus('Tarayıcı izni bekleniyor...', 'loading');
      try {
        await enablePushNotifications(state.vapidPublicKey);
        state.preferences.push_enabled = true;
        render();
        renderStatus('Push bildirimi aktif.', 'success');
      } catch (error) {
        renderStatus(error.message || 'Push izni alınamadı.', 'error');
      }
    });
    root.querySelector('[data-send-test-notification]')?.addEventListener('click', async () => {
      renderStatus('Test bildirimi hazırlanıyor...', 'loading');
      try {
        await sendTestNotification();
        renderStatus('Test bildirimi kuyruğa alındı.', 'success');
        toast('Test bildirimi kuyruğa alındı.', 'success');
      } catch (error) {
        renderStatus(error.message || 'Test bildirimi başarısız.', 'error');
      }
    });
    root.querySelector('[data-refresh-scheduled]')?.addEventListener('click', async () => {
      const res = await fetchScheduledNotifications();
      state.scheduled = res.data || [];
      render();
    });
  }

  return { load, render };
}
