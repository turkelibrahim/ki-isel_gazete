import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const NotificationService = require('../../services/notificationService.js');
const AnnouncementService = require('../../services/announcementService.js');
const { renderEmailTemplate, stripHtml } = require('../../services/emailService.js');

function db() {
  return {
    users: [{ id: 'user_demo', name: 'Demo', email: 'demo@example.com' }],
    notificationPreferences: [],
    pushSubscriptions: [],
    scheduledNotifications: [],
    announcements: [],
    notificationLogs: []
  };
}

test('default preferences are created and updateable', () => {
  const store = db();
  const pref = NotificationService.getNotificationPreferences(store, 'user_demo');
  assert.equal(pref.email_enabled, true);
  assert.equal(pref.push_enabled, false);
  const updated = NotificationService.updateNotificationPreferences(store, 'user_demo', { push_enabled: true, one_hour_before_enabled: false });
  assert.equal(updated.push_enabled, true);
  assert.equal(updated.one_hour_before_enabled, false);
});

test('push subscription is saved once per endpoint', () => {
  const store = db();
  const raw = { endpoint: 'https://push.example/1', keys: { p256dh: 'abc', auth: 'def' } };
  NotificationService.subscribePush(store, 'user_demo', raw, { userAgent: 'test' });
  NotificationService.subscribePush(store, 'user_demo', raw, { userAgent: 'test2' });
  assert.equal(store.pushSubscriptions.length, 1);
  assert.equal(store.pushSubscriptions[0].is_active, true);
  assert.equal(NotificationService.getNotificationPreferences(store, 'user_demo').push_enabled, true);
});

test('notification times skip past entries during announcement scheduling', () => {
  const store = db();
  NotificationService.updateNotificationPreferences(store, 'user_demo', { email_enabled: true, push_enabled: false });
  const result = AnnouncementService.createAnnouncement(store, {
    title: 'Kritik bakım',
    description: 'Sistem bakımı',
    is_critical: true,
    event_date: new Date(Date.now() + 2 * 3600000).toISOString()
  });
  assert.equal(result.success, true);
  const types = store.scheduledNotifications.map((n) => n.notification_type);
  assert.equal(types.includes('one_day_before'), false);
  assert.equal(types.includes('one_hour_before'), true);
  assert.equal(types.includes('critical_announcement'), true);
});

test('duplicate notification is not created twice', () => {
  const store = db();
  const payload = { user_id: 'user_demo', announcement_id: 'a1', notification_type: 'immediate', channel: 'email', title: 'A', scheduled_at: new Date().toISOString() };
  const first = NotificationService.createNotificationIfNotExists(store, payload);
  const second = NotificationService.createNotificationIfNotExists(store, payload);
  assert.equal(first.created, true);
  assert.equal(second.created, false);
  assert.equal(store.scheduledNotifications.length, 1);
});

test('scheduler marks missing SMTP email as retry then failed after max retry', async () => {
  const store = db();
  NotificationService.createNotificationIfNotExists(store, { user_id: 'user_demo', notification_type: 'system', channel: 'email', title: 'Test', scheduled_at: new Date().toISOString() });
  for (let i = 0; i < 3; i += 1) {
    store.scheduledNotifications[0].scheduled_at = new Date(Date.now() - 1000).toISOString();
    await NotificationService.processDueNotifications(store, { limit: 5 });
  }
  assert.equal(store.scheduledNotifications[0].status, 'failed');
  assert.match(store.scheduledNotifications[0].error_message, /SMTP|nodemailer|e-posta/i);
});

test('event reminders create one day and one hour notifications when future', () => {
  const store = db();
  NotificationService.updateNotificationPreferences(store, 'user_demo', { email_enabled: true });
  const result = NotificationService.scheduleNotificationsForEvent(store, {
    id: 'event_1',
    title: 'Konser',
    event_date: new Date(Date.now() + 48 * 3600000).toISOString()
  }, 'user_demo');
  assert.equal(result.created >= 2, true);
  assert.equal(store.scheduledNotifications.some((n) => n.event_id === 'event_1'), true);
});

test('HTML email template escapes user data and keeps Turkish characters', () => {
  const html = renderEmailTemplate({ title: '<Kritik> Çalışma', message: 'Türkçe duyuru & güvenlik', notification_type: 'critical_announcement', target_url: '/duyuru' });
  assert.match(html, /&lt;Kritik&gt; Çalışma/);
  assert.match(stripHtml(html), /Türkçe duyuru/);
});

test('updating announcement cancels old pending notifications', () => {
  const store = db();
  const created = AnnouncementService.createAnnouncement(store, { title: 'Duyuru', is_critical: true, event_date: new Date(Date.now() + 48 * 3600000).toISOString() });
  const before = store.scheduledNotifications.filter((n) => n.status === 'pending').length;
  AnnouncementService.updateAnnouncement(store, created.announcement.id, { event_date: new Date(Date.now() + 72 * 3600000).toISOString() });
  assert.equal(before > 0, true);
  assert.equal(store.scheduledNotifications.some((n) => n.status === 'cancelled'), true);
});
