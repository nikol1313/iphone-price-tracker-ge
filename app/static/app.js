const state = {
  products: [],
  tracked: [],
  selectedId: null,
  visibleCount: 10,
  currentPage: "overview",
  token: sessionStorage.getItem("priceMonitorToken"),
  email: sessionStorage.getItem("priceMonitorEmail"),
  authMode: "login",
};

// Remove credentials saved by the previous browser-only implementation.
localStorage.removeItem("telegramBotToken");
localStorage.removeItem("telegramChatId");

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const pages = new Set(["overview", "products", "alerts"]);
const pageTitles = {
  overview: "Overview",
  products: "Products",
  alerts: "Alerts",
};
const money = (value, currency = "GEL") => value == null
  ? "No price"
  : new Intl.NumberFormat("en", { style: "currency", currency }).format(Number(value));
const dateTime = (value) => value
  ? new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
  : "Not available";
const safeUrl = value => {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch {
    return "#";
  }
};
const escapeHtml = (value = "") => String(value).replace(/[&<>"']/g, char => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
})[char]);
const productName = product => {
  const brand = String(product?.brand || "").trim();
  const model = String(product?.model || "").trim();
  return model.toLowerCase().startsWith(brand.toLowerCase()) ? model : [brand, model].filter(Boolean).join(" ");
};
const variant = product => product ? [product.storage, product.color].filter(Boolean).join(" · ") || "Storage and color not specified" : "Storage and color not specified";

function pageFromLocation() {
  const requestedPage = new URLSearchParams(window.location.search).get("page");
  return pages.has(requestedPage) ? requestedPage : "overview";
}

function showPage(page, updateHistory = false) {
  const nextPage = pages.has(page) ? page : "overview";
  state.currentPage = nextPage;

  $$("[data-page-view]").forEach(view => {
    view.hidden = view.dataset.pageView !== nextPage;
  });
  $$(".nav-link[data-page-link]").forEach(link => {
    const isCurrent = link.dataset.pageLink === nextPage;
    link.classList.toggle("active", isCurrent);
    if (isCurrent) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });

  document.title = `${pageTitles[nextPage]} — Price Monitor`;
  if (updateHistory) {
    const url = new URL(window.location.href);
    url.searchParams.set("page", nextPage);
    url.hash = "";
    window.history.pushState({ page: nextPage }, "", url);
  }
  window.scrollTo(0, 0);
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body) headers["Content-Type"] = "application/json";
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, { ...options, headers });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map(item => item.msg).join(", ")
      : data.detail || "Unknown error";
    const error = new Error(detail || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return data;
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 2800);
}

async function loadProducts(query = "") {
  state.visibleCount = 10;
  const grid = $("#productGrid");
  grid.innerHTML = '<div class="loading-state">Loading products from the API…</div>';
  try {
    const endpoint = query ? `/search?q=${encodeURIComponent(query)}&limit=100` : "/products?limit=100";
    const page = await api(endpoint);
    $("#apiStatus").innerHTML = "<span></span>API connected";
    state.products = Array.isArray(page.items) ? page.items : [];
    renderProducts(page.total);
    $("#clearSearch").hidden = !query;
    if (!query && state.products && state.products.length) {
      const priced = state.products.find(item => item.lowest_price != null) || state.products[0];
      selectProduct(priced.id);
    }
  } catch (error) {
    $("#apiStatus").innerHTML = "<span></span>API unavailable";
    grid.innerHTML = `<div class="empty-state">Could not load products.<br>${escapeHtml(error.message)}</div>`;
    $("#productCount").textContent = "Unavailable";
  }
}

function renderProducts(total = state.products?.length || 0) {
  $("#productCount").textContent = `${total} ${total === 1 ? "product" : "products"}`;
  const grid = $("#productGrid");
  const showMore = $("#showMoreButton");
  if (!state.products || !state.products.length) {
    grid.innerHTML = '<div class="empty-state">No products match this search.</div>';
    showMore.hidden = true;
    return;
  }
  const visibleProducts = state.products.slice(0, state.visibleCount);
  showMore.hidden = state.visibleCount >= state.products.length;
  showMore.textContent = `Show more (${state.products.length - state.visibleCount} remaining)`;
  grid.innerHTML = visibleProducts.map(product => `
    <article class="product-card ${product.id === state.selectedId ? "selected" : ""}" data-product-id="${product.id}" tabindex="0">
      <h3>${escapeHtml(productName(product))}</h3>
      <div class="price-row">
        <div class="price">
          <strong>${escapeHtml(money(product.lowest_price, product.currency || "GEL"))}</strong>
        </div>
      </div>
    </article>
  `).join("");
}

async function selectProduct(productId) {
  state.selectedId = Number(productId);
  const product = state.products && state.products.find(item => item.id === state.selectedId);
  if (!product) return;
  $$(".product-card").forEach(card => card.classList.toggle("selected", Number(card.dataset.productId) === state.selectedId));
  $("#historySection").hidden = false;
  $("#storesSection").hidden = false;
  $("#historyTitle").textContent = productName(product);
  $("#historyVariant").textContent = variant(product);
  updateSelectedActions();
  $("#historySummary").innerHTML = `
    <div class="summary-item"><span>Current low</span><strong>${escapeHtml(money(product.lowest_price, product.currency || "GEL"))}</strong></div>
    <div class="summary-item"><span>Listings</span><strong>${product.listing_count}</strong></div>
  `;
  try {
    const [prices, listings] = await Promise.all([
      api(`/products/${product.id}/prices?limit=100`),
      api(`/products/${product.id}/listings?limit=100`),
    ]);
    renderChart(prices.items, product);
    renderListings(listings.items);
  } catch (error) {
    showToast(error.message);
  }
}

function renderChart(items, product) {
  const svg = $("#priceChart");
  const empty = $("#chartEmpty");
  if (!items || !items.length) {
    if (product.lowest_price != null) {
      empty.hidden = true;
      renderCurrentSnapshot(svg, product);
    } else {
      svg.innerHTML = "";
      empty.textContent = "Price history will appear after the first price is recorded.";
      empty.hidden = false;
    }
    return;
  }
  empty.hidden = true;
  const ordered = [...items].sort((a, b) => new Date(a.recorded_at) - new Date(b.recorded_at));
  const values = ordered.map(item => Number(item.price));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const padding = Math.max((max - min) * .18, max * .025, 1);
  const low = min - padding;
  const high = max + padding;
  const W = 1000, H = 320, left = 72, right = 24, top = 28, bottom = 45;
  const plotW = W - left - right, plotH = H - top - bottom;
  const x = index => left + (ordered.length === 1 ? plotW / 2 : index * plotW / (ordered.length - 1));
  const y = value => top + (high - value) * plotH / (high - low || 1);
  const points = ordered.map((item, i) => `${x(i)},${y(Number(item.price))}`).join(" ");
  const area = `${left},${H-bottom} ${points} ${x(ordered.length-1)},${H-bottom}`;
  const currency = ordered[0].currency;
  const grid = [0, .25, .5, .75, 1].map(step => {
    const gy = top + plotH * step;
    const label = high - (high - low) * step;
    return `<line class="chart-grid" x1="${left}" y1="${gy}" x2="${W-right}" y2="${gy}"/>
      <text class="chart-label" x="12" y="${gy + 4}">${escapeHtml(money(label, currency))}</text>`;
  }).join("");
  const dots = ordered.map((item, i) => `
    <circle class="chart-dot" cx="${x(i)}" cy="${y(Number(item.price))}" r="4">
      <title>${escapeHtml(item.store_name)} — ${escapeHtml(money(item.price, item.currency))} — ${escapeHtml(dateTime(item.recorded_at))}</title>
    </circle>`).join("");
  const firstDate = new Date(ordered[0].recorded_at);
  const lastDate = new Date(ordered.at(-1).recorded_at);
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = `
    <defs><linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#10B981" stop-opacity=".18"/><stop offset="1" stop-color="#10B981" stop-opacity="0"/></linearGradient></defs>
    ${grid}<polygon class="chart-area" points="${area}"/><polyline class="chart-line" points="${points}"/>${dots}
    <text class="chart-label" x="${left}" y="${H-16}">${firstDate.toLocaleDateString()}</text>
    <text class="chart-label" text-anchor="end" x="${W-right}" y="${H-16}">${lastDate.toLocaleDateString()}</text>`;

  $("#historySummary").insertAdjacentHTML("beforeend", `
    <div class="summary-item"><span>Recorded low</span><strong>${escapeHtml(money(min, currency))}</strong></div>
    <div class="summary-item"><span>Recorded high</span><strong>${escapeHtml(money(max, currency))}</strong></div>
  `);
}

function renderCurrentSnapshot(svg, product) {
  const W = 1000, H = 320, left = 72, right = 24;
  const centerY = 165;
  const label = money(product.lowest_price, product.currency || "GEL");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = `
    <line class="chart-grid" x1="${left}" y1="60" x2="${W-right}" y2="60"/>
    <line class="chart-snapshot-line" x1="${left}" y1="${centerY}" x2="${W-right}" y2="${centerY}"/>
    <line class="chart-grid" x1="${left}" y1="270" x2="${W-right}" y2="270"/>
    <circle class="chart-snapshot" cx="${W/2}" cy="${centerY}" r="8"/>
    <text class="chart-note" text-anchor="middle" x="${W/2}" y="${centerY-25}">${escapeHtml(label)}</text>
    <text class="chart-label" text-anchor="middle" x="${W/2}" y="${centerY+38}">Current lowest price · history not recorded yet</text>`;
}

function renderListings(items) {
  const body = $("#storesBody");
  $("#storesEmpty").hidden = items && items.length > 0;
  if (!items || !items.length) {
    body.innerHTML = "";
    return;
  }
  body.innerHTML = items.map(item => `
    <tr>
      <td><strong>${escapeHtml(item.store_name)}</strong></td>
      <td>${escapeHtml(money(item.current_price, item.currency))}</td>
      <td><span class="status ${item.is_available ? "" : "unavailable"}">${item.is_available ? "Available" : "Unavailable"}</span></td>
      <td>${escapeHtml(dateTime(item.last_checked_at))}</td>
      <td><a class="store-link" href="${escapeHtml(safeUrl(item.product_url))}" target="_blank" rel="noopener noreferrer" aria-label="Open listing at ${escapeHtml(item.store_name)}"><svg><use href="#i-external"/></svg></a></td>
    </tr>`).join("");
}

async function loadTracked() {
  updateAccount();
  if (!state.token) {
    state.tracked = [];
    return;
  }
  try {
    const page = await api("/tracked-products?limit=100");
    state.tracked = Array.isArray(page.items) ? page.items : [];
    renderTracked();
    renderProducts();
    updateSelectedActions();
  } catch (error) {
    if (error.status === 401) logout(false);
    else showToast(error.message);
  }
}

function renderTracked() {
  const content = $("#trackedContent");
  if (!state.tracked || !state.tracked.length) {
    content.innerHTML = "<p>You are signed in. Track a product to keep it in this list.</p>";
    return;
  }
  content.innerHTML = `<div class="tracked-list">${state.tracked.map(item => `
    <div class="tracked-row">
      <div><h3>${escapeHtml(productName(item.product))}</h3><p>${escapeHtml(variant(item.product))}</p></div>
      <div>
        <p>${escapeHtml(money(item.product.lowest_price, item.product.currency || "GEL"))} current low</p>
        ${item.active_alert
          ? `<p class="alert-value">Target: ${escapeHtml(money(item.active_alert.target_price, item.active_alert.currency))}${item.active_alert.is_triggered ? " · Reached" : ""}</p>`
          : "<p>No active alert</p>"}
      </div>
      <button class="small-button" type="button" data-untrack="${item.product.id}">Stop tracking</button>
    </div>`).join("")}</div>`;
}

function updateAccount() {
  const button = $("#accountButton");
  if (state.token) {
    button.innerHTML = `<svg><use href="#i-logout"/></svg><span>${escapeHtml(state.email || "Sign out")}</span>`;
  } else {
    button.innerHTML = '<svg><use href="#i-user"/></svg><span>Sign in</span>';
    $("#trackedContent").innerHTML = '<p>Sign in to track products and create price alerts.</p><button class="primary-button" type="button" data-open-auth>Sign in</button>';
  }
}

function updateSelectedActions() {
  const tracked = state.tracked.some(item => item.product.id === state.selectedId);
  const button = $("#selectedTrackButton");
  button.textContent = tracked ? "Stop tracking" : "Track";
  button.classList.toggle("tracked", tracked);
  button.disabled = state.selectedId == null;
  $("#selectedAlertButton").disabled = state.selectedId == null;
}

function openAuth() {
  $("#authError").textContent = "";
  $("#authDialog").showModal();
}

function openAlert(productId) {
  if (!state.token) {
    openAuth();
    showToast("Sign in before creating an alert.");
    return;
  }
  const product = (state.products && state.products.find(item => item.id === Number(productId)))
    || (state.tracked && state.tracked.find(item => item.product.id === Number(productId))?.product);
  if (!product) return;
  $("#alertTitle").textContent = `${product.model} target`;
  const form = $("#alertForm");
  form.product_id.value = product.id;
  form.currency.value = product.currency || "GEL";
  form.target_price.value = product.lowest_price || "";
  $("#alertError").textContent = "";
  $("#alertDialog").showModal();
}

async function openSettings() {
  if (!state.token) {
    openAuth();
    showToast("Sign in to configure Telegram notifications.");
    return;
  }

  const form = $("#settingsForm");
  $("#settingsError").textContent = "";
  $("#settingsSuccess").textContent = "";
  $("#settingsDialog").showModal();
  try {
    const settings = await api("/notification-settings/telegram");
    form.telegram_chat_id.value = settings.telegram_chat_id || "";
  } catch (error) {
    $("#settingsError").textContent = error.message;
  }
}

async function track(productId) {
  if (!state.token) {
    openAuth();
    showToast("Sign in before tracking a product.");
    return;
  }
  const tracked = state.tracked && state.tracked.some(item => item.product.id === Number(productId));
  try {
    if (tracked) await api(`/tracked-products/${productId}`, { method: "DELETE" });
    else await api("/tracked-products", { method: "POST", body: JSON.stringify({ product_id: Number(productId) }) });
    showToast(tracked ? "Product removed from tracking." : "Product is now tracked.");
    await loadTracked();
  } catch (error) {
    showToast(error.message);
  }
}

function logout(notify = true) {
  state.token = null;
  state.email = null;
  state.tracked = [];
  sessionStorage.removeItem("priceMonitorToken");
  sessionStorage.removeItem("priceMonitorEmail");
  updateAccount();
  renderProducts();
  updateSelectedActions();
  if (notify) showToast("Signed out.");
}

$("#searchForm").addEventListener("submit", event => {
  event.preventDefault();
  const query = $("#searchInput").value.trim();
  if (query && query.length >= 2) loadProducts(query);
});
$("#clearSearch").addEventListener("click", () => {
  $("#searchInput").value = "";
  loadProducts();
});
$("#showMoreButton").addEventListener("click", () => {
  state.visibleCount += 10;
  renderProducts();
});
$("#productGrid").addEventListener("click", event => {
  const card = event.target.closest("[data-product-id]");
  if (card) selectProduct(card.dataset.productId);
});
$("#productGrid").addEventListener("keydown", event => {
  if ((event.key === "Enter" || event.key === " ") && event.target.matches("[data-product-id]")) {
    event.preventDefault();
    selectProduct(event.target.dataset.productId);
  }
});
$("#trackedContent").addEventListener("click", event => {
  const untrack = event.target.closest("[data-untrack]");
  if (untrack) track(untrack.dataset.untrack);
  if (event.target.closest("[data-open-auth]")) openAuth();
});
$("#accountButton").addEventListener("click", () => state.token ? logout() : openAuth());
$("#settingsButton").addEventListener("click", () => openSettings());
$("#selectedTrackButton").addEventListener("click", () => state.selectedId && track(state.selectedId));
$("#selectedAlertButton").addEventListener("click", () => state.selectedId && openAlert(state.selectedId));
$("#closeAuth").addEventListener("click", () => $("#authDialog").close());
$("#closeAlert").addEventListener("click", () => $("#alertDialog").close());
$("#closeSettings").addEventListener("click", () => $("#settingsDialog").close());
$("#authMode").addEventListener("click", () => {
  state.authMode = state.authMode === "login" ? "register" : "login";
  const registering = state.authMode === "register";
  $("#authTitle").textContent = registering ? "Create account" : "Sign in";
  $("#authForm button[type=submit]").textContent = registering ? "Create account" : "Sign in";
  $("#authMode").textContent = registering ? "Already have an account? Sign in" : "Create an account";
  $("#authError").textContent = "";
});
$("#authForm").addEventListener("submit", async event => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const credentials = { email: form.get("email"), password: form.get("password") };
  const submit = $("button[type=submit]", event.currentTarget);
  submit.disabled = true;
  $("#authError").textContent = "";
  try {
    if (state.authMode === "register") await api("/auth/register", { method: "POST", body: JSON.stringify(credentials) });
    const token = await api("/auth/login", { method: "POST", body: JSON.stringify(credentials) });
    state.token = token.access_token;
    state.email = credentials.email;
    sessionStorage.setItem("priceMonitorToken", state.token);
    sessionStorage.setItem("priceMonitorEmail", state.email);
    $("#authDialog").close();
    showToast(state.authMode === "register" ? "Account created and signed in." : "Signed in.");
    await loadTracked();
  } catch (error) {
    $("#authError").textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});
$("#alertForm").addEventListener("submit", async event => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  $("#alertError").textContent = "";
  try {
    await api(`/products/${form.get("product_id")}/alerts`, {
      method: "POST",
      body: JSON.stringify({ target_price: form.get("target_price"), currency: form.get("currency") }),
    });
    $("#alertDialog").close();
    showToast("Price alert created.");
    await loadTracked();
  } catch (error) {
    $("#alertError").textContent = error.message;
  }
});
$("#settingsForm").addEventListener("submit", async event => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const chatId = form.get("telegram_chat_id").trim();

  $("#settingsError").textContent = "";
  $("#settingsSuccess").textContent = "";

  try {
    await api("/notification-settings/telegram", {
      method: "PUT",
      body: JSON.stringify({ telegram_chat_id: chatId || null }),
    });
    $("#settingsSuccess").textContent = chatId
      ? "Telegram notifications enabled."
      : "Telegram notifications disabled.";
    setTimeout(() => $("#settingsDialog").close(), 1000);
  } catch (error) {
    $("#settingsError").textContent = error.message;
  }
});
document.addEventListener("click", event => {
  const pageLink = event.target.closest("[data-page-link]");
  if (pageLink && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
    event.preventDefault();
    showPage(pageLink.dataset.pageLink, true);
    if (pageLink.hasAttribute("data-focus-search")) {
      requestAnimationFrame(() => $("#searchInput")?.focus());
    }
    return;
  }
  if (event.target.closest("[data-open-auth]")) openAuth();
});
window.addEventListener("popstate", () => showPage(pageFromLocation()));

showPage(pageFromLocation());
loadProducts();
loadTracked();
