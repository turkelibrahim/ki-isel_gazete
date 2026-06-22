"use strict";

const NotificationService = require("./notificationService");

let timer = null;
let running = false;

function startNotificationScheduler(options = {}) {
  if (String(process.env.NOTIFICATIONS_ENABLED || "true").toLowerCase() === "false") return { started: false, reason: "disabled" };
  if (timer) return { started: false, reason: "already_running" };
  const intervalMs = Math.max(1000, Number(process.env.NOTIFICATION_SCHEDULER_INTERVAL_MS || 60000));
  const readDb = options.readDb;
  const writeDb = options.writeDb;
  if (typeof readDb !== "function" || typeof writeDb !== "function") return { started: false, reason: "missing_db_handlers" };
  async function tick() {
    if (running) return;
    running = true;
    try {
      const db = readDb();
      const result = await NotificationService.processDueNotifications(db, { limit: 50 });
      if (result.processed > 0) writeDb(db);
    } catch (error) {
      if (options.logWarn) options.logWarn("notification-scheduler", "tick failed", error.message || String(error));
    } finally {
      running = false;
    }
  }
  timer = setInterval(tick, intervalMs);
  timer.unref?.();
  setTimeout(tick, 100).unref?.();
  return { started: true, intervalMs };
}

function stopNotificationScheduler() {
  if (timer) clearInterval(timer);
  timer = null;
  running = false;
}

module.exports = { startNotificationScheduler, stopNotificationScheduler, _internal: { isRunning: () => Boolean(timer) } };
