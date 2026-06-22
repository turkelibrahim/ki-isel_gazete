import { subscribePush } from './notificationApi.js';

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  return Uint8Array.from([...rawData].map((char) => char.charCodeAt(0)));
}

export function browserSupportsPush() {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}

export async function enablePushNotifications(vapidPublicKey = '') {
  if (!browserSupportsPush()) throw new Error('Tarayıcınız push bildirimlerini desteklemiyor.');
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new Error('Bildirim izni verilmedi.');
  const registration = await navigator.serviceWorker.register('/public/service-worker.js');
  if (!vapidPublicKey) throw new Error('VAPID public key eksik.');
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
  });
  await subscribePush(subscription.toJSON());
  return subscription;
}
