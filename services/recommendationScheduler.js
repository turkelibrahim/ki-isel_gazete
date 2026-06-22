"use strict";

const RecommendationService = require("./recommendationService");

let schedulerHandle = null;

function startRecommendationScheduler({ readDb, writeDb, logWarn = console.warn, intervalMs } = {}) {
  if (schedulerHandle || process.env.RECOMMENDATION_SCHEDULER_ENABLED === "false") return schedulerHandle;
  const cadence = Math.max(60_000, Number(intervalMs || process.env.RECOMMENDATION_SCHEDULER_INTERVAL_MS || 30 * 60 * 1000) || 30 * 60 * 1000);
  schedulerHandle = setInterval(() => {
    try {
      const db = readDb();
      RecommendationService.recomputeAll(db);
      writeDb(db);
    } catch (error) {
      logWarn("recommendation-scheduler", "recommendation recompute failed", error.message || String(error));
    }
  }, cadence);
  schedulerHandle.unref?.();
  return schedulerHandle;
}

function stopRecommendationScheduler() {
  if (schedulerHandle) clearInterval(schedulerHandle);
  schedulerHandle = null;
}

module.exports = { startRecommendationScheduler, stopRecommendationScheduler };
