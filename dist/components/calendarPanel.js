import { escapeHtml } from "../utils/textUtils.js";
import {
  getCalendarEvents,
  addCalendarEvent,
  removeCalendarEvent,
  setEventReminder,
  isEventInCalendar,
  findCalendarEntryByEventId
} from "../utils/calendarStore.js";
import { computeReminderAt } from "../utils/reminderManager.js";

let _showToast = () => {};
let _showPage = null;
let panelState = {
  currentDate: new Date(),
  selectedDayKey: fmtDay(new Date()),
  embeddedContainer: null
};

export function initCalendarPanel(showToastFn, showPageFn) {
  _showToast = showToastFn || (() => {});
  _showPage = showPageFn || null;
}

export async function renderCalendarPage(container) {
  if (!container) return;
  panelState.embeddedContainer = container;
  await renderCalendarPanel(container, { embedded: true });
}

export async function openCalendarPanel() {
  let overlay = document.getElementById("calendar-panel-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "calendar-panel-overlay";
    overlay.className = "calendar-panel-overlay";
    overlay.innerHTML = `<div class="calendar-panel-shell"><div class="calendar-panel" id="calendar-panel-root"></div></div>`;
    document.body.appendChild(overlay);

    overlay.addEventListener("click", (event) => {
      if (event.target === overlay || event.target.classList.contains("calendar-panel-shell")) {
        closeCalendarPanel();
      }
    });
  }

  overlay.hidden = false;
  document.body.classList.add("calendar-panel-open");
  const root = overlay.querySelector("#calendar-panel-root");
  await renderCalendarPanel(root, { embedded: false });
}

export function closeCalendarPanel() {
  const overlay = document.getElementById("calendar-panel-overlay");
  if (overlay) overlay.hidden = true;
  document.body.classList.remove("calendar-panel-open");
}

async function renderCalendarPanel(root, { embedded = false } = {}) {
  const events = await getCalendarEvents();
  const now = new Date();
  const monthStart = new Date(panelState.currentDate.getFullYear(), panelState.currentDate.getMonth(), 1);
  const monthLabel = monthStart.toLocaleDateString("tr-TR", { month: "long", year: "numeric" });
  const selectedDay = panelState.selectedDayKey;
  const upcomingEvents = [...events]
    .sort((a, b) => new Date(a.eventDate) - new Date(b.eventDate))
    .filter((event) => !isNaN(new Date(event.eventDate).getTime()));
  const filteredEvents = selectedDay
    ? upcomingEvents.filter((event) => fmtDay(new Date(event.eventDate)) === selectedDay)
    : upcomingEvents;

  root.innerHTML = `
    <div class="calendar-panel-inner ${embedded ? "is-embedded" : ""}">
      <div class="calendar-panel-header">
        <div class="calendar-panel-title">
          <i class="fa-regular fa-calendar-days"></i>
          <div>
            <h2>Benim Takvimim</h2>
            <p>Kişisel gazete takvimin ve yaklaşan etkinliklerin</p>
          </div>
        </div>
        <div class="calendar-panel-actions">
          <button type="button" class="calendar-nav-btn calendar-nav-today" data-calendar-action="today">Bugün</button>
          ${embedded ? "" : `<button type="button" class="calendar-panel-close" data-calendar-action="close" aria-label="Kapat"><i class="fa-solid fa-xmark"></i></button>`}
        </div>
      </div>

      <div class="calendar-layout">
        <section class="calendar-month-card">
          <div class="calendar-month-head">
            <button type="button" class="calendar-nav-btn" data-calendar-action="prev-month" aria-label="Önceki ay"><i class="fa-solid fa-chevron-left"></i></button>
            <strong>${escapeHtml(capitalize(monthLabel))}</strong>
            <button type="button" class="calendar-nav-btn" data-calendar-action="next-month" aria-label="Sonraki ay"><i class="fa-solid fa-chevron-right"></i></button>
          </div>
          ${renderMonthCalendar(events, monthStart, selectedDay, now)}
        </section>

        <section class="upcoming-events">
          <div class="upcoming-events-head">
            <h3>Yaklaşan Etkinlikler</h3>
            <button type="button" class="calendar-inline-add-btn" data-calendar-action="open-events">+ Etkinlik Ekle</button>
          </div>
          <div class="upcoming-events-list">
            ${renderUpcomingEvents(filteredEvents.length ? filteredEvents : upcomingEvents, { emptyForSelectedDay: Boolean(selectedDay) })}
          </div>
          <div class="reminder-status-card">
            <div class="reminder-status-copy">
              <span class="reminder-status-icon"><i class="fa-regular fa-bell"></i></span>
              <div>
                <strong>Hatırlatıcı</strong>
                <p>Tüm etkinlikler için hatırlatıcılar 30 dakika önce aktif olacak.</p>
              </div>
            </div>
            <span class="reminder-status-badge"><i class="fa-solid fa-check"></i> Hatırlatıcılar aktif</span>
          </div>
        </section>
      </div>

      <div class="calendar-footer">
        <div class="calendar-footer-note"><i class="fa-regular fa-calendar-check"></i><span>Etkinlik takvimine eklendi</span></div>
        <button type="button" class="calendar-footer-btn" data-calendar-action="view-calendar">Takvimi Görüntüle <i class="fa-solid fa-arrow-up-right-from-square"></i></button>
      </div>
    </div>
  `;

  bindCalendarPanelEvents(root, embedded);
}

function bindCalendarPanelEvents(root, embedded) {
  root.querySelector('[data-calendar-action="close"]')?.addEventListener("click", closeCalendarPanel);

  root.querySelectorAll("[data-calendar-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.calendarAction;
      if (action === "today") {
        panelState.currentDate = new Date();
        panelState.selectedDayKey = fmtDay(new Date());
        return renderCalendarPanel(root, { embedded });
      }
      if (action === "prev-month") {
        panelState.currentDate = new Date(panelState.currentDate.getFullYear(), panelState.currentDate.getMonth() - 1, 1);
        return renderCalendarPanel(root, { embedded });
      }
      if (action === "next-month") {
        panelState.currentDate = new Date(panelState.currentDate.getFullYear(), panelState.currentDate.getMonth() + 1, 1);
        return renderCalendarPanel(root, { embedded });
      }
      if (action === "open-events") {
        if (_showPage) _showPage("events");
        closeCalendarPanel();
        _showToast("Etkinliklerden takvimine ekleme yapabilirsin.", "info");
      }
      if (action === "view-calendar") {
        if (_showPage) _showPage("my-calendar");
        closeCalendarPanel();
      }
    });
  });

  root.querySelectorAll(".calendar-day[data-day-key]").forEach((button) => {
    button.addEventListener("click", () => {
      panelState.selectedDayKey = button.dataset.dayKey;
      renderCalendarPanel(root, { embedded });
    });
  });

  root.querySelectorAll("[data-calendar-reminder]").forEach((button) => {
    button.addEventListener("click", async () => {
      const eventId = button.dataset.calendarReminder;
      const entry = (await getCalendarEvents()).find((event) => event.id === eventId);
      if (entry) showReminderSetupModal(entry, () => renderCalendarPanel(root, { embedded }));
    });
  });

  root.querySelectorAll("[data-calendar-remove]").forEach((button) => {
    button.addEventListener("click", async () => {
      await removeCalendarEvent(button.dataset.calendarRemove);
      _showToast("Etkinlik takvimden kaldırıldı.", "info");
      renderCalendarPanel(root, { embedded });
    });
  });

  root.querySelectorAll("[data-calendar-menu-toggle]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const menuId = button.dataset.calendarMenuToggle;
      root.querySelectorAll(".calendar-event-menu").forEach((menu) => {
        menu.hidden = menu.id !== menuId ? true : !menu.hidden;
      });
    });
  });

  document.addEventListener("click", closeOpenCalendarMenus, { once: true });
}

function closeOpenCalendarMenus() {
  document.querySelectorAll(".calendar-event-menu").forEach((menu) => {
    menu.hidden = true;
  });
}

export function renderMonthCalendar(events, monthStart, selectedDayKey, now = new Date()) {
  const eventsByDay = new Map();
  for (const event of events) {
    const key = fmtDay(new Date(event.eventDate));
    if (!eventsByDay.has(key)) eventsByDay.set(key, []);
    eventsByDay.get(key).push(event);
  }

  const firstDay = new Date(monthStart.getFullYear(), monthStart.getMonth(), 1);
  const startIndex = (firstDay.getDay() + 6) % 7;
  const gridStart = new Date(firstDay);
  gridStart.setDate(firstDay.getDate() - startIndex);

  const weekdays = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
  const cells = [];

  for (let i = 0; i < 42; i += 1) {
    const day = new Date(gridStart);
    day.setDate(gridStart.getDate() + i);
    const key = fmtDay(day);
    const isToday = fmtDay(now) === key;
    const isSelected = selectedDayKey === key;
    const isCurrentMonth = day.getMonth() === monthStart.getMonth();
    const hasEvent = eventsByDay.has(key);
    cells.push(`
      <button type="button" class="calendar-day ${isToday ? "is-today" : ""} ${isSelected ? "is-selected" : ""} ${hasEvent ? "has-event" : ""} ${isCurrentMonth ? "" : "is-muted"}" data-day-key="${key}">
        <span class="calendar-day-label">${day.getDate()}</span>
        ${hasEvent ? `<span class="calendar-day-dot"></span>` : ""}
      </button>
    `);
  }

  return `
    <div class="calendar-weekdays">${weekdays.map((name) => `<span>${name}</span>`).join("")}</div>
    <div class="calendar-grid">${cells.join("")}</div>
  `;
}

export function renderUpcomingEvents(events, { emptyForSelectedDay = false } = {}) {
  const sorted = [...events]
    .sort((a, b) => new Date(a.eventDate) - new Date(b.eventDate))
    .slice(0, 8);

  if (!sorted.length) {
    return `<div class="calendar-empty-state"><i class="fa-regular fa-calendar-xmark"></i><p>${emptyForSelectedDay ? "Bu gün için etkinlik bulunmuyor." : "Henüz takvimine etkinlik eklemedin."}</p></div>`;
  }

  return sorted.map((event) => {
    const eventDate = new Date(event.eventDate);
    const datePart = isNaN(eventDate.getTime()) ? "" : eventDate.toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });
    const timePart = event.eventTime || (!isNaN(eventDate.getTime()) ? eventDate.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }) : "");
    const menuId = `calendar-menu-${event.id}`;
    return `
      <article class="upcoming-event-card">
        <div class="upcoming-event-main">
          <span class="calendar-category-dot" style="--dot-color:${categoryColor(event.category)}"></span>
          <div class="upcoming-event-content">
            <h4>${escapeHtml(event.title)}</h4>
            <div class="upcoming-event-meta">
              <span>${escapeHtml(datePart)}</span>
              <span>•</span>
              <span>${escapeHtml(timePart)}</span>
            </div>
            <p>${escapeHtml(event.description || event.userNote || "")}</p>
          </div>
        </div>
        <div class="upcoming-event-side">
          <button type="button" class="calendar-icon-btn ${event.reminderEnabled ? "is-active" : ""}" data-calendar-reminder="${escapeHtml(event.id)}" title="Hatırlatıcı Kur"><i class="fa-regular fa-bell"></i></button>
          <div class="calendar-menu-wrap">
            <button type="button" class="calendar-icon-btn" data-calendar-menu-toggle="${menuId}" title="Diğer işlemler"><i class="fa-solid fa-ellipsis-vertical"></i></button>
            <div class="calendar-event-menu" id="${menuId}" hidden>
              <button type="button" data-calendar-remove="${escapeHtml(event.id)}"><i class="fa-solid fa-trash-can"></i> Kaldır</button>
              ${event.url ? `<a href="${escapeHtml(event.url)}" target="_blank" rel="noopener"><i class="fa-solid fa-arrow-up-right-from-square"></i> Aç</a>` : ""}
            </div>
          </div>
        </div>
      </article>
    `;
  }).join("");
}

function categoryColor(category = "") {
  const value = String(category).toLowerCase();
  if (value.includes("ekonomi") || value.includes("finans")) return "#b42318";
  if (value.includes("spor")) return "#1d4ed8";
  if (value.includes("kültür") || value.includes("sanat")) return "#7c3aed";
  if (value.includes("teknoloji")) return "#0f766e";
  return "#d33a2c";
}

function capitalize(text) {
  return String(text || "").replace(/^./, (char) => char.toLocaleUpperCase("tr-TR"));
}

function fmtDay(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export async function showAddToCalendarModal(eventData, onDone) {
  showEventPlannerModal({
    mode: "add",
    eventData,
    onDone
  });
}

export async function showReminderSetupModal(eventData, onDone) {
  showEventPlannerModal({
    mode: "reminder",
    eventData,
    onDone
  });
}

function showEventPlannerModal({ mode = "add", eventData, onDone }) {
  const existing = document.getElementById("cal-add-modal-overlay");
  if (existing) existing.remove();

  const overlay = document.createElement("div");
  overlay.id = "cal-add-modal-overlay";
  overlay.className = "cal-modal-overlay";
  overlay.innerHTML = `
    <div class="cal-modal">
      <div class="cal-modal-header">
        <h3><i class="fa-regular fa-calendar-plus"></i> ${mode === "add" ? "Takvime Ekle" : "Hatırlatıcı Kur"}</h3>
        <button type="button" class="cal-modal-close" aria-label="Kapat"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="cal-modal-body">
        <div class="cal-modal-event-preview">
          <h4>${escapeHtml(eventData.title || "")}</h4>
          <p>${escapeHtml(eventData.displayDate || eventData.date || eventData.eventDate || "")}</p>
          ${(eventData.venue || eventData.location) ? `<p><i class="fa-solid fa-location-dot"></i> ${escapeHtml(eventData.venue || eventData.location || "")}${eventData.city ? ", " + escapeHtml(eventData.city) : ""}</p>` : ""}
        </div>
        <div class="cal-modal-field">
          <label for="cal-modal-reminder">Hatırlatıcı</label>
          <select id="cal-modal-reminder" class="cal-modal-select">
            <option value="at_time">Etkinlik anında</option>
            <option value="15min" selected>15 dakika önce</option>
            <option value="1hour">1 saat önce</option>
            <option value="1day">1 gün önce</option>
            <option value="custom">Özel tarih/saat seç</option>
          </select>
          <input type="datetime-local" id="cal-modal-custom-time" class="cal-modal-input" hidden>
        </div>
        ${mode === "add" ? `
        <div class="cal-modal-field">
          <label for="cal-modal-note">Not (isteğe bağlı)</label>
          <input type="text" id="cal-modal-note" class="cal-modal-input" placeholder="Kısa not ekle..." maxlength="200">
        </div>` : ""}
      </div>
      <div class="cal-modal-footer">
        <button type="button" class="cal-modal-btn cal-modal-btn-cancel">İptal</button>
        <button type="button" class="cal-modal-btn cal-modal-btn-save"><i class="fa-solid fa-check"></i> Kaydet</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  const reminderSelect = overlay.querySelector("#cal-modal-reminder");
  const customTimeInput = overlay.querySelector("#cal-modal-custom-time");
  reminderSelect.addEventListener("change", () => {
    customTimeInput.hidden = reminderSelect.value !== "custom";
  });

  const close = () => overlay.remove();
  overlay.querySelector(".cal-modal-close").addEventListener("click", close);
  overlay.querySelector(".cal-modal-btn-cancel").addEventListener("click", close);
  overlay.addEventListener("click", (event) => { if (event.target === overlay) close(); });

  overlay.querySelector(".cal-modal-btn-save").addEventListener("click", async () => {
    const reminderOption = reminderSelect.value;
    const sourceDate = eventData.date || eventData.eventDate || new Date().toISOString();
    let reminderAt = null;
    if (reminderOption === "custom") {
      reminderAt = customTimeInput.value ? new Date(customTimeInput.value).toISOString() : null;
    } else {
      reminderAt = computeReminderAt(sourceDate, reminderOption);
    }

    let entry = eventData.id ? await findCalendarEntryByEventId(eventData.eventId || eventData.id) : null;

    if (!entry) {
      const note = overlay.querySelector("#cal-modal-note")?.value?.trim() || "";
      entry = await addCalendarEvent({
        ...eventData,
        eventId: eventData.eventId || eventData.id,
        userNote: note,
        reminderAt: mode === "add" ? reminderAt : null
      });
    }

    if (reminderAt) {
      entry = await setEventReminder(entry.id, reminderAt) || entry;
    }

    close();
    _showToast(mode === "add" ? "Etkinlik takvimine eklendi." : "Hatırlatıcı ayarlandı.", "success");
    if (onDone) onDone(entry);
  });
}

export { isEventInCalendar, findCalendarEntryByEventId };
