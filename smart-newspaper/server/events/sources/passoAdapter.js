const { sampleEventsForSource } = require("./_sampleEvents");

const source = {
  name: 'Passo',
  type: "adapter",
  url: "",
  categories: ["konser", "tiyatro", "festival", "stand-up", "spor", "sergi", "çocuk"]
};

async function fetchEvents(options = {}) {
  // Adapter is intentionally isolated: source/network errors must not break the aggregator.
  // Live scraping/API mapping can be extended here without touching the rest of the system.
  return sampleEventsForSource(source.name);
}

module.exports = { source, fetchEvents };
