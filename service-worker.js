self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch { data = {}; }
  const title = data.title || "SmartNewspaper Bildirimi";
  const options = {
    body: data.body || data.message || "",
    icon: data.icon || "/assets/sources/default-news.svg",
    badge: data.badge || "/assets/sources/default-news.svg",
    data: { url: data.url || "/" }
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || "/";
  event.waitUntil(clients.openWindow(targetUrl));
});
