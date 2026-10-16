/* Authentication, price alert, and notification forms. */
import { $, api, showToast, state } from "./core.js";
import { loadTracked } from "./account.js";

export function openAuth() {
  $("#authError").textContent = "";
  $("#authDialog").showModal();
}

export function openAlert(productId) {
  if (!state.token) {
    openAuth();
    showToast("Sign in before creating an alert.");
    return;
  }
  const product = state.products.find(item => item.id === Number(productId))
    || state.tracked.find(item => item.product.id === Number(productId))?.product;
  if (!product) return;
  $("#alertTitle").textContent = `${product.model} target`;
  const form = $("#alertForm");
  form.product_id.value = product.id;
  form.currency.value = product.currency || "GEL";
  form.target_price.value = product.lowest_price || "";
  $("#alertError").textContent = "";
  $("#alertDialog").showModal();
}

export async function openTelegramSettings() {
  if (!state.token) {
    openAuth();
    showToast("Sign in to configure Telegram notifications.");
    return;
  }
  const form = $("#telegramForm");
  $("#telegramError").textContent = "";
  $("#telegramSuccess").textContent = "";
  closeAccountMenu();
  $("#telegramDialog").showModal();
  try {
    const settings = await api("/notification-settings/telegram");
    form.telegram_chat_id.value = settings.telegram_chat_id || "";
    state.notificationSettings = settings;
  } catch (error) {
    $("#telegramError").textContent = error.message;
  }
}

export function openEmailSettings() {
  closeAccountMenu();
  if (!state.token) {
    openAuth();
    showToast("Sign in to view email notification settings.");
    return;
  }
  $("#accountEmailInput").value = state.email || "";
  $("#emailDialog").showModal();
}

function closeAccountMenu() {
  $("#accountMenu").hidden = true;
  $("#accountButton").setAttribute("aria-expanded", "false");
}

function bindAuthentication() {
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
}

function bindAlertForm() {
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
}

function bindTelegramForm() {
  $("#telegramForm").addEventListener("submit", async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const chatId = form.get("telegram_chat_id").trim();
    $("#telegramError").textContent = "";
    $("#telegramSuccess").textContent = "";
    try {
      await api("/notification-settings/telegram", {
        method: "PUT",
        body: JSON.stringify({ telegram_chat_id: chatId || null }),
      });
      $("#telegramSuccess").textContent = chatId
        ? "Telegram notifications enabled."
        : "Telegram notifications disabled.";
      setTimeout(() => $("#telegramDialog").close(), 1000);
    } catch (error) {
      $("#telegramError").textContent = error.message;
    }
  });
}

export function bindDialogs() {
  $("#closeAuth").addEventListener("click", () => $("#authDialog").close());
  $("#closeAlert").addEventListener("click", () => $("#alertDialog").close());
  $("#closeTelegram").addEventListener("click", () => $("#telegramDialog").close());
  $("#closeEmail").addEventListener("click", () => $("#emailDialog").close());
  $("#closeEmailDone").addEventListener("click", () => $("#emailDialog").close());
  bindAuthentication();
  bindAlertForm();
  bindTelegramForm();
}
