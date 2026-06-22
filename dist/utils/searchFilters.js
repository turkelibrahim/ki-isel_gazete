export function debounce(fn, delay = 300) {
  let timer = null;
  return function debounced(...args) {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn.apply(this, args), delay);
  };
}

export const SEARCH_CATEGORY_MAP = Object.freeze({
  gundem: { type: "special", value: "trend_or_latest" },
  politika: { type: "label", value: "Siyaset" },
  magazin: { type: "label", value: "Eğlence" },
  saglik: { type: "label", value: "Sağlık" },
  spor: { type: "label", value: "Spor" },
  teknoloji: { type: "label", value: "Teknoloji" }
});
