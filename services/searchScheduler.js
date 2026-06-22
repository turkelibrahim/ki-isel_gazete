const SearchService = require("./searchService");

let schedulerHandle = null;

function startSearchScheduler({ readDb, writeDb, logWarn = () => {}, intervalMs } = {}) {
  if (schedulerHandle || process.env.SEARCH_TREND_SCHEDULER_ENABLED === "false") return schedulerHandle;
  const ms = Math.max(60_000, Number(intervalMs || process.env.SEARCH_TREND_SCHEDULER_INTERVAL_MS || 15 * 60_000));
  const run = () => {
    try {
      const db = readDb();
      SearchService.initSearchDb(db);
      SearchService.calculateTrendScores(db);
      writeDb(db);
    } catch (error) {
      logWarn("search-scheduler", "trend score update failed", error.message || String(error));
    }
  };
  schedulerHandle = setInterval(run, ms);
  schedulerHandle.unref?.();
  setTimeout(run, 1000).unref?.();
  return schedulerHandle;
}

function stopSearchScheduler() {
  if (schedulerHandle) clearInterval(schedulerHandle);
  schedulerHandle = null;
}

module.exports = { startSearchScheduler, stopSearchScheduler };
