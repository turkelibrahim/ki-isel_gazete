"use strict";

let webpush = null;
try { webpush = require("web-push"); } catch { webpush = null; }

function hasVapidConfig() {
  return Boolean(process.env.VAPID_PUBLIC_KEY && process.env.VAPID_PRIVATE_KEY && process.env.VAPID_SUBJECT);
}

function configureWebPush() {
  if (!webpush || !hasVapidConfig()) return false;
  webpush.setVapidDetails(process.env.VAPID_SUBJECT, process.env.VAPID_PUBLIC_KEY, process.env.VAPID_PRIVATE_KEY);
  return true;
}

function subscriptionToWebPushPayload(subscription = {}) {
  return {
    endpoint: subscription.endpoint,
    keys: {
      p256dh: subscription.p256dh_key || subscription.p256dhKey || subscription.keys?.p256dh,
      auth: subscription.auth_key || subscription.authKey || subscription.keys?.auth
    }
  };
}

async function sendPushNotification(notification = {}, context = {}) {
  const db = context.db || {};
  const userId = String(notification.user_id || notification.userId || "user_demo");
  const subscriptions = (db.pushSubscriptions || []).filter((item) => String(item.user_id || item.userId) === userId && item.is_active !== false);
  if (!subscriptions.length) throw new Error("Aktif push subscription bulunamadı.");
  if (!configureWebPush()) throw new Error("VAPID veya web-push yapılandırması eksik; push kanalı devre dışı.");
  const payload = JSON.stringify({
    title: notification.title || "SmartNewspaper Bildirimi",
    body: notification.message || "",
    message: notification.message || "",
    icon: "/assets/sources/default-news.svg",
    badge: "/assets/sources/default-news.svg",
    url: notification.target_url || notification.targetUrl || "/"
  });
  let sent = 0;
  for (const sub of subscriptions) {
    try {
      await webpush.sendNotification(subscriptionToWebPushPayload(sub), payload);
      sent += 1;
    } catch (error) {
      if (error.statusCode === 404 || error.statusCode === 410) {
        sub.is_active = false;
        sub.updated_at = new Date().toISOString();
      } else {
        throw error;
      }
    }
  }
  if (!sent) throw new Error("Aktif push subscription bulunamadı veya tüm endpointler pasifleşti.");
  return { success: true, sent };
}

module.exports = { hasVapidConfig, configureWebPush, sendPushNotification, subscriptionToWebPushPayload };
