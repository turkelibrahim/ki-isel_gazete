const FEEDBACK_TYPES = ["Öneri", "Hata Bildirimi", "Şikayet", "Yeni Özellik", "Memnuniyet", "Genel Mesaj"];
const FEEDBACK_PRIORITIES = ["Düşük", "Normal", "Önemli", "Acil"];
const STATUS_CLASS = {
  "Gönderildi": "sent",
  "Görüldü": "seen",
  "İnceleniyor": "reviewing",
  "Cevaplandı": "replied",
  "Çözüldü": "resolved",
  "Kapatıldı": "closed"
};

function esc(value = "") {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function deviceType() {
  return /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent || "") ? "Mobil" : "Masaüstü";
}

function pageNameFromState(state = {}) {
  const active = state.activePage || "feed";
  const labels = {
    feed: "Ana Sayfa",
    events: "Etkinlikler",
    sources: "Kaynaklarım",
    trends: "Trendler",
    profile: "Profil",
    egazete: "E-Gazete"
  };
  return labels[active] || active;
}

function formatDate(value) {
  try {
    return new Date(value).toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return value || "—";
  }
}

function buildOptions(values, selected = "") {
  return values.map((value) => `<option value="${esc(value)}"${value === selected ? " selected" : ""}>${esc(value)}</option>`).join("");
}

function buildMarkup() {
  return `
    <button type="button" class="feedback-fab" id="feedback-fab" aria-label="Geri Bildirim Gönder" title="Geri Bildirim Gönder">
      <i class="fa-solid fa-comment-dots" aria-hidden="true"></i>
      <span class="feedback-fab-tooltip">Geri Bildirim Gönder</span>
    </button>

    <div class="feedback-modal" id="feedback-modal" hidden>
      <div class="feedback-backdrop" data-feedback-close></div>
      <section class="feedback-dialog" role="dialog" aria-modal="true" aria-labelledby="feedback-title" tabindex="-1">
        <button type="button" class="feedback-close" data-feedback-close aria-label="Geri bildirim penceresini kapat">
          <i class="fa-solid fa-xmark" aria-hidden="true"></i>
        </button>
        <div class="feedback-head">
          <div class="feedback-head-icon"><i class="fa-solid fa-comment-dots" aria-hidden="true"></i></div>
          <div>
            <p class="feedback-kicker">Kullanıcı & Admin iletişimi</p>
            <h2 id="feedback-title">Görüşünü Bizimle Paylaş</h2>
            <p>Kişisel gazeteni daha iyi hale getirmek için görüşlerin bizim için önemli.</p>
          </div>
        </div>

        <div class="feedback-tabs" role="tablist">
          <button type="button" class="active" data-feedback-tab="form" role="tab">Geri Bildirim Gönder</button>
          <button type="button" data-feedback-tab="messages" role="tab">Mesajlarım</button>
        </div>

        <div class="feedback-status" id="feedback-status" aria-live="polite"></div>

        <form class="feedback-pane active" id="feedback-form" data-feedback-pane="form">
          <label class="feedback-field">
            <span>Konu</span>
            <input type="text" name="subject" maxlength="160" placeholder="Kısa ve net bir başlık girin" autocomplete="off" />
          </label>

          <div class="feedback-grid">
            <label class="feedback-field">
              <span>Geri Bildirim Türü</span>
              <select name="type" required>
                <option value="">Seçiniz</option>
                ${buildOptions(FEEDBACK_TYPES)}
              </select>
            </label>
            <label class="feedback-field">
              <span>Öncelik</span>
              <select name="priority">
                ${buildOptions(FEEDBACK_PRIORITIES, "Normal")}
              </select>
            </label>
          </div>

          <div class="feedback-rating-row">
            <span>Memnuniyet</span>
            <div class="feedback-stars" role="radiogroup" aria-label="Memnuniyet puanı">
              ${[1,2,3,4,5].map((value) => `<button type="button" data-feedback-star="${value}" aria-label="${value} yıldız"><i class="fa-regular fa-star"></i></button>`).join("")}
            </div>
            <input type="hidden" name="rating" value="0" />
          </div>

          <label class="feedback-field">
            <span>Mesaj</span>
            <textarea name="message" maxlength="1000" rows="6" placeholder="Görüş ve önerilerinizi detaylı olarak yazabilirsiniz..."></textarea>
            <small class="feedback-counter" id="feedback-counter">0 / 1000</small>
          </label>

          <button class="feedback-submit" type="submit">
            <i class="fa-solid fa-paper-plane" aria-hidden="true"></i>
            <span>Gönder</span>
          </button>
        </form>

        <div class="feedback-pane feedback-messages-pane" data-feedback-pane="messages">
          <div class="feedback-messages-toolbar">
            <strong>Önceki mesajların</strong>
            <button type="button" id="feedback-refresh-messages"><i class="fa-solid fa-rotate"></i> Yenile</button>
          </div>
          <div class="feedback-messages" id="feedback-messages"></div>
        </div>
      </section>
    </div>
  `;
}

export function initFeedbackFloatingButton({ api, showToast, getState }) {
  if (document.getElementById("feedback-center-root")) return;
  const root = document.createElement("div");
  root.id = "feedback-center-root";
  root.innerHTML = buildMarkup();
  document.body.appendChild(root);

  const fab = root.querySelector("#feedback-fab");
  const modal = root.querySelector("#feedback-modal");
  const dialog = root.querySelector(".feedback-dialog");
  const form = root.querySelector("#feedback-form");
  const status = root.querySelector("#feedback-status");
  const counter = root.querySelector("#feedback-counter");
  const messagesWrap = root.querySelector("#feedback-messages");
  const submitButton = root.querySelector(".feedback-submit");
  let activeRating = 0;
  let lastFocus = null;

  function setStatus(message = "", type = "") {
    status.textContent = message;
    status.className = `feedback-status ${type ? `feedback-status-${type}` : ""}`;
  }

  function isLoggedIn() {
    const state = getState?.() || {};
    return Boolean(state.authToken || localStorage.getItem("newspaperAuthToken"));
  }

  function openModal(tab = "form") {
    if (!isLoggedIn()) {
      showToast?.("Geri bildirim göndermek için giriş yapmalısın.", "error");
      return;
    }
    lastFocus = document.activeElement;
    modal.hidden = false;
    document.body.classList.add("feedback-open");
    switchTab(tab);
    requestAnimationFrame(() => dialog.focus());
    if (tab === "messages") loadMessages();
  }

  function closeModal() {
    modal.hidden = true;
    document.body.classList.remove("feedback-open");
    setStatus("");
    if (lastFocus && typeof lastFocus.focus === "function") lastFocus.focus();
  }

  function switchTab(tab) {
    root.querySelectorAll("[data-feedback-tab]").forEach((button) => button.classList.toggle("active", button.dataset.feedbackTab === tab));
    root.querySelectorAll("[data-feedback-pane]").forEach((pane) => pane.classList.toggle("active", pane.dataset.feedbackPane === tab));
    if (tab === "messages") loadMessages();
  }

  function setRating(value) {
    activeRating = Number(value) || 0;
    form.elements.rating.value = String(activeRating);
    root.querySelectorAll("[data-feedback-star]").forEach((button) => {
      const selected = Number(button.dataset.feedbackStar) <= activeRating;
      const icon = button.querySelector("i");
      icon.className = selected ? "fa-solid fa-star" : "fa-regular fa-star";
      button.classList.toggle("active", selected);
    });
  }

  function validate(subject, type, message) {
    if (!subject || subject.length < 3) return "Konu en az 3 karakter olmalı.";
    if (!type) return "Geri bildirim türü seçmelisin.";
    if (!message || message.length < 10) return "Mesaj en az 10 karakter olmalı.";
    if (message.length > 1000) return "Mesaj en fazla 1000 karakter olabilir.";
    return "";
  }

  function renderMessages(items = []) {
    if (!messagesWrap) return;
    if (!items.length) {
      messagesWrap.innerHTML = `
        <div class="feedback-empty">
          <i class="fa-regular fa-message"></i>
          <strong>Henüz mesaj göndermedin</strong>
          <p>Geri bildirim gönderdiğinde geçmişin burada görünecek.</p>
        </div>`;
      return;
    }
    messagesWrap.innerHTML = items.map((item) => `
      <article class="feedback-message-card">
        <div class="feedback-message-top">
          <div>
            <strong>${esc(item.subject)}</strong>
            <p>${esc(item.type)} · ${esc(item.priority)} · ${formatDate(item.createdAt)}</p>
          </div>
          <span class="feedback-badge feedback-badge-${STATUS_CLASS[item.status] || "sent"}">${esc(item.status || "Gönderildi")}</span>
        </div>
        <p class="feedback-message-preview">${esc((item.message || "").slice(0, 180))}${(item.message || "").length > 180 ? "…" : ""}</p>
        ${item.adminReply ? `<div class="feedback-admin-reply"><i class="fa-solid fa-reply"></i><span>${esc(item.adminReply.slice(0, 220))}${item.adminReply.length > 220 ? "…" : ""}</span></div>` : ""}
      </article>
    `).join("");
  }

  async function loadMessages() {
    if (!isLoggedIn()) return;
    messagesWrap.innerHTML = `<div class="feedback-loading"><i class="fa-solid fa-spinner fa-spin"></i> Mesajların yükleniyor...</div>`;
    try {
      const payload = await api("/api/feedback/my?page=1&page_size=30");
      renderMessages(payload.items || []);
    } catch (error) {
      messagesWrap.innerHTML = `<div class="feedback-empty feedback-error"><i class="fa-solid fa-triangle-exclamation"></i><strong>Mesajlar alınamadı</strong><p>${esc(error.message || "Lütfen tekrar dene.")}</p></div>`;
    }
  }

  fab.addEventListener("click", () => openModal("form"));
  root.querySelectorAll("[data-feedback-close]").forEach((button) => button.addEventListener("click", closeModal));
  root.querySelectorAll("[data-feedback-tab]").forEach((button) => button.addEventListener("click", () => switchTab(button.dataset.feedbackTab)));
  root.querySelectorAll("[data-feedback-star]").forEach((button) => button.addEventListener("click", () => setRating(button.dataset.feedbackStar)));
  root.querySelector("#feedback-refresh-messages")?.addEventListener("click", loadMessages);

  form.elements.message.addEventListener("input", () => {
    counter.textContent = `${form.elements.message.value.length} / 1000`;
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) closeModal();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!isLoggedIn()) {
      showToast?.("Geri bildirim göndermek için giriş yapmalısın.", "error");
      return;
    }
    const subject = form.elements.subject.value.trim();
    const type = form.elements.type.value;
    const priority = form.elements.priority.value || "Normal";
    const message = form.elements.message.value.trim();
    const error = validate(subject, type, message);
    if (error) { setStatus(error, "error"); return; }

    const state = getState?.() || {};
    const body = {
      subject,
      type,
      priority,
      rating: activeRating,
      message,
      meta: {
        pageName: pageNameFromState(state),
        currentUrl: window.location.href,
        userAgent: navigator.userAgent,
        deviceType: deviceType(),
        articleId: state.activeArticleId || state.selectedArticleId || "",
        eventId: state.activeEventId || "",
        screen: `${window.innerWidth}x${window.innerHeight}`,
        language: navigator.language || "tr"
      }
    };

    submitButton.disabled = true;
    submitButton.classList.add("loading");
    setStatus("Gönderiliyor...", "info");
    try {
      const payload = await api("/api/feedback", { method: "POST", body: JSON.stringify(body) });
      form.reset();
      setRating(0);
      counter.textContent = "0 / 1000";
      setStatus(payload.message || "Geri bildirimin admin’e ulaştı. Teşekkür ederiz.", "success");
      showToast?.("Geri bildirimin admin’e ulaştı. Teşekkür ederiz.", "success");
      loadMessages();
    } catch (error) {
      setStatus(error.message || "Geri bildirim gönderilemedi.", "error");
      showToast?.(error.message || "Geri bildirim gönderilemedi.", "error");
    } finally {
      submitButton.disabled = false;
      submitButton.classList.remove("loading");
    }
  });

  window.openFeedbackCenter = openModal;
}
