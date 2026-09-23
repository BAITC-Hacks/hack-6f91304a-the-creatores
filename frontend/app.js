"use strict";

// Integration map only. No API requests are made in this standalone prototype.
const API_ENDPOINTS = Object.freeze({
  upload: { method: "POST", path: "/api/upload" },
  calculate: { method: "POST", path: "/api/calculate" },
  recommendations: { method: "GET", path: "/api/recommendations" },
  chat: { method: "POST", path: "/api/chat" },
  export: { method: "GET", path: "/api/export" },
});

// Fixed fixtures, not a forecasting or procurement calculation algorithm.
const MOCK_PRODUCTS = [
  { sku: "TEST-001", name: "Кабель силовой", supplier: "ИЭК", stock: 50, incoming_in_period: 40, forecast_demand: 180, safety_stock: 30, recommended_qty: 120, unit: "шт", urgency: "high", reason: "Остатка и ожидаемой поставки недостаточно для покрытия прогнозируемого спроса.", warnings: [] },
  { sku: "TEST-002", name: "Автоматический выключатель C16", supplier: "Schneider Electric", stock: 24, incoming_in_period: 20, forecast_demand: 100, safety_stock: 14, recommended_qty: 70, unit: "шт", urgency: "high", reason: "Запас выключателей необходимо пополнить для покрытия ожидаемого спроса.", warnings: ["Уточните срок доставки у поставщика."] },
  { sku: "TEST-003", name: "Контактор 25 А", supplier: "ABB", stock: 12, incoming_in_period: 0, forecast_demand: 42, safety_stock: 10, recommended_qty: 40, unit: "шт", urgency: "high", reason: "Текущий запас ограничен, подтверждённых поставок в периоде нет.", warnings: ["Нет подтверждённых поступлений в плановом периоде."] },
  { sku: "TEST-004", name: "Розетка с заземлением", supplier: "EKF", stock: 80, incoming_in_period: 40, forecast_demand: 150, safety_stock: 20, recommended_qty: 50, unit: "шт", urgency: "medium", reason: "Плановое пополнение позволит сохранить страховой запас.", warnings: [] },
  { sku: "TEST-005", name: "Щит распределительный", supplier: "ИЭК", stock: 15, incoming_in_period: 10, forecast_demand: 40, safety_stock: 5, recommended_qty: 20, unit: "шт", urgency: "medium", reason: "Ожидаемые поступления покрывают только часть плановой потребности.", warnings: [] },
  { sku: "TEST-006", name: "УЗО 40 А / 30 мА", supplier: "Schneider Electric", stock: 30, incoming_in_period: 10, forecast_demand: 45, safety_stock: 10, recommended_qty: 15, unit: "шт", urgency: "low", reason: "Рекомендуется небольшое плановое пополнение для поддержания резерва.", warnings: [] },
  { sku: "TEST-007", name: "Клемма соединительная", supplier: "ABB", stock: 300, incoming_in_period: 50, forecast_demand: 200, safety_stock: 50, recommended_qty: 0, unit: "шт", urgency: "low", reason: "Остаток и ожидаемая поставка покрывают спрос и страховой запас. Дополнительный заказ не требуется.", warnings: [] },
  { sku: "TEST-008", name: "DIN-рейка 35 мм", supplier: "EKF", stock: 120, incoming_in_period: 0, forecast_demand: 80, safety_stock: 20, recommended_qty: 0, unit: "шт", urgency: "low", reason: "Текущего остатка достаточно для покрытия плановой потребности.", warnings: [] },
];
const URGENCY = { high: "Высокая", medium: "Средняя", low: "Низкая" };
const state = { file: null, products: [], calculating: false, chatting: false, revision: 0 };
const $ = (id) => document.getElementById(id);
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const normalize = (value) => value.toLocaleLowerCase("ru-RU").replaceAll("ё", "е").trim();
const escapeHTML = (value) => String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);

// Replace these methods with upload (FormData), calculate, recommendations,
// and chat API calls when integrating. Rendering is independent of transport.
const dataService = {
  async calculate(file) {
    if (!file) throw new Error("Файл не выбран");
    await delay(1100);
    return MOCK_PRODUCTS.map((product) => ({ ...product, warnings: [...product.warnings] }));
  },
  async chat(question, products) {
    await delay(550);
    return getMockChatResponse(question, products);
  },
};

function showNotification(message, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  $("notifications").append(toast);
  while ($("notifications").children.length > 4) $("notifications").firstElementChild.remove();
  setTimeout(() => toast.remove(), 5000);
}

function resetFilters() {
  $("search").value = "";
  $("supplier-filter").value = "";
  $("urgency-filter").value = "";
  renderRecommendations();
}

function handleFileSelect(file) {
  if (!file || state.calculating) return;
  state.revision += 1;
  state.file = null;
  state.products = [];
  $("drop-zone").classList.remove("success", "error");
  $("step-review").classList.remove("current");
  $("step-export").classList.remove("current");
  $("step-upload").classList.add("current");
  populateSupplierFilter();
  resetFilters();
  updateStatistics();
  if (!/\.(xlsx|xls)$/i.test(file.name)) {
    $("file-input").value = "";
    $("drop-zone").classList.add("error");
    $("file-status").textContent = "Неподдерживаемый формат файла. Выберите .xlsx или .xls.";
    $("calculation-status").textContent = "Выберите Excel-файл, чтобы продолжить";
    showNotification("Неподдерживаемый формат файла", "error");
    return;
  }
  state.file = file;
  $("drop-zone").classList.add("success");
  $("file-status").textContent = `✓ ${file.name} · файл выбран`;
  $("calculation-status").textContent = "Файл готов. Можно рассчитать рекомендации.";
  showNotification("Файл успешно выбран");
}

async function calculateRecommendations() {
  if (state.calculating) return;
  if (!state.file) {
    showNotification("Сначала выберите Excel-файл", "error");
    $("choose-file").focus();
    return;
  }
  state.calculating = true;
  state.revision += 1;
  state.products = [];
  populateSupplierFilter();
  resetFilters();
  updateStatistics();
  for (const id of ["calculate", "choose-file", "file-input", "export"]) $(id).disabled = true;
  $("calculate").textContent = "Выполняется расчёт…";
  $("calculation-status").textContent = "Подготавливаем демонстрационные рекомендации…";
  $("system-status").textContent = "Выполняется расчёт";
  $("recommendations").setAttribute("aria-busy", "true");
  try {
    state.products = await dataService.calculate(state.file);
    populateSupplierFilter();
    renderRecommendations();
    updateStatistics();
    $("step-upload").classList.remove("current");
    $("step-review").classList.add("current");
    $("step-export").classList.remove("current");
    $("calculation-status").textContent = "✓ Рекомендации успешно рассчитаны · тестовые данные";
    showNotification("Рекомендации успешно рассчитаны");
    $("recommendations").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    $("calculation-status").textContent = "Не удалось получить рекомендации. Попробуйте ещё раз.";
    showNotification("Ошибка расчёта. Попробуйте ещё раз.", "error");
  } finally {
    state.calculating = false;
    for (const id of ["calculate", "choose-file", "file-input", "export"]) $(id).disabled = false;
    $("calculate").textContent = "✧ Рассчитать рекомендации";
    $("system-status").textContent = "Система готова";
    $("recommendations").setAttribute("aria-busy", "false");
    renderRecommendations();
  }
}

function updateStatistics() {
  $("stat-total").textContent = state.products.length;
  $("stat-order").textContent = state.products.filter((p) => p.recommended_qty > 0).length;
  $("stat-urgent").textContent = state.products.filter((p) => p.urgency === "high").length;
  $("stat-suppliers").textContent = new Set(state.products.map((p) => p.supplier)).size;
}

function populateSupplierFilter() {
  const select = $("supplier-filter");
  const previous = select.value;
  select.replaceChildren(new Option("Все поставщики", ""));
  [...new Set(state.products.map((p) => p.supplier))].forEach((supplier) => select.add(new Option(supplier, supplier)));
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
}

function applyFilters() {
  const query = normalize($("search").value);
  return state.products.filter((p) =>
    (!$("supplier-filter").value || p.supplier === $("supplier-filter").value) &&
    (!$("urgency-filter").value || p.urgency === $("urgency-filter").value) &&
    (!query || [p.sku, p.name, p.supplier].some((value) => normalize(value).includes(query)))
  );
}

function urgencyBadge(urgency) {
  const level = Object.hasOwn(URGENCY, urgency) ? urgency : "low";
  return `<span class="badge ${level}"><span aria-hidden="true">${{ high: "↑", medium: "–", low: "↓" }[level]}</span>${URGENCY[level]}</span>`;
}

function renderRecommendations() {
  const products = applyFilters();
  $("recommendation-rows").innerHTML = products.map((p) => `<tr>
    <td>${escapeHTML(p.sku)}</td><td>${escapeHTML(p.name)}</td><td>${escapeHTML(p.supplier)}</td>
    <td>${escapeHTML(p.stock)}</td><td>${escapeHTML(p.incoming_in_period)}</td><td>${escapeHTML(p.forecast_demand)}</td><td>${escapeHTML(p.safety_stock)}</td>
    <td><span class="${p.recommended_qty > 0 ? "quantity" : ""}">${escapeHTML(p.recommended_qty)}</span></td><td>${escapeHTML(p.unit)}</td>
    <td>${urgencyBadge(p.urgency)}</td><td><button class="details-button" type="button" data-sku="${escapeHTML(p.sku)}" aria-label="Подробнее о ${escapeHTML(p.name)}">Подробнее →</button></td></tr>`).join("");
  $("result-count").textContent = products.length;
  $("empty-state").hidden = products.length > 0;
  const title = state.calculating ? "Подготавливаем рекомендации…" : state.products.length ? "Ничего не найдено" : "Здесь появится ваш план закупок";
  const description = state.calculating ? "Это займёт несколько секунд." : state.products.length ? "Измените условия поиска или сбросьте фильтры." : "Загрузите Excel-файл и рассчитайте рекомендации.";
  $("empty-state").querySelector("h3").textContent = title;
  $("empty-state").querySelector("p").textContent = description;
  $("table-summary").textContent = state.products.length ? `Показано ${products.length} из ${state.products.length} · К заказу: ${products.filter((p) => p.recommended_qty > 0).length}` : "Данные ещё не загружены";
}

function openProductDetails(sku) {
  const p = state.products.find((product) => product.sku === sku);
  if (!p) return;
  const metrics = [["Текущий остаток", p.stock], ["Товар в пути", p.incoming_in_period], ["Прогноз спроса", p.forecast_demand], ["Страховой запас", p.safety_stock], ["Рекомендуемое количество", p.recommended_qty]];
  // Explanatory arithmetic only; never used to produce recommended_qty.
  const baseNeed = p.forecast_demand + p.safety_stock - p.stock - p.incoming_in_period;
  $("product-details").innerHTML = `<h2 id="product-title">${escapeHTML(p.name)}</h2>
    <p class="product-subtitle">${escapeHTML(p.sku)} · ${escapeHTML(p.supplier)} · Единица: ${escapeHTML(p.unit)}</p>${urgencyBadge(p.urgency)}
    <dl class="detail-grid">${metrics.map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHTML(value)} ${escapeHTML(p.unit)}</dd></div>`).join("")}</dl>
    <h3>Причина рекомендации</h3><p class="detail-copy">${escapeHTML(p.reason)}</p>
    <div class="explanation"><h3>Объяснение базовой потребности</h3><p>Прогноз спроса + Страховой запас − Текущий остаток − Товар в пути = Базовая потребность</p><p class="formula">${p.forecast_demand} + ${p.safety_stock} − ${p.stock} − ${p.incoming_in_period} = ${baseNeed} ${escapeHTML(p.unit)}</p><p>${baseNeed < 0 ? "Отрицательная базовая потребность означает избыток запаса; заказ не требуется. " : ""}Финальное значение в будущем может учитывать дополнительные бизнес-правила backend, например MOQ (минимальный объём заказа).</p></div>
    <h3>Предупреждения</h3>${p.warnings.length ? `<ul class="warnings">${p.warnings.map((warning) => `<li>${escapeHTML(warning)}</li>`).join("")}</ul>` : '<p class="detail-copy">Предупреждений нет.</p>'}`;
  $("product-dialog").showModal();
}

function getMockChatResponse(question, products) {
  if (!products.length) return "Сначала загрузите Excel-файл и выполните расчёт. После этого я смогу объяснить рекомендации.";
  const query = normalize(question);
  const product = products.find((p) => query.includes(normalize(p.sku)) || query.includes(normalize(p.name)));
  if (product) {
    const p = product;
    return `${p.name} (${p.sku}): прогноз спроса — ${p.forecast_demand} ${p.unit}, текущий остаток — ${p.stock} ${p.unit}, товар в пути — ${p.incoming_in_period} ${p.unit}, страховой запас — ${p.safety_stock} ${p.unit}.\n\n${p.recommended_qty > 0 ? `Рекомендуется заказать ${p.recommended_qty} ${p.unit}.` : "Заказ не требуется: рекомендованное количество — 0."} ${p.reason}${p.warnings.length ? `\n\nОбратите внимание: ${p.warnings.join(" ")}` : ""}`;
  }
  if (/сроч|приоритет/.test(query)) {
    const urgent = products.filter((p) => p.urgency === "high");
    return urgent.length ? `Высокий приоритет у следующих позиций:\n${urgent.map((p) => `• ${p.sku} — ${p.name}: ${p.recommended_qty} ${p.unit}, поставщик ${p.supplier}.`).join("\n")}\n\nПроверьте сроки поставки перед формированием заказа.` : "В текущих рекомендациях нет позиций с высокой срочностью.";
  }
  return "Я могу объяснить рекомендацию по SKU или полному названию товара, а также показать срочные позиции. Например: «Почему нужно заказать TEST-001?» или «Какие позиции самые срочные?»";
}

function appendChatMessage(text, role) {
  const message = document.createElement("div");
  message.className = `message ${role}`;
  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = role === "user" ? "Вы" : "ЗакупAI · демо";
  const content = document.createElement("p");
  content.textContent = text;
  message.append(label, content);
  $("chat-messages").append(message);
  $("chat-messages").scrollTop = $("chat-messages").scrollHeight;
  return message;
}

async function sendChatMessage(event) {
  event.preventDefault();
  const question = $("chat-input").value.trim();
  if (!question || state.chatting) return;
  state.chatting = true;
  const revision = state.revision;
  $("send-chat").disabled = true;
  appendChatMessage(question, "user");
  $("chat-input").value = "";
  const pending = appendChatMessage("Готовлю объяснение…", "assistant");
  try {
    const response = await dataService.chat(question, state.products);
    pending.remove();
    appendChatMessage(revision === state.revision ? response : "Набор данных изменился. Задайте вопрос повторно после завершения расчёта.", "assistant");
  } catch (error) {
    pending.remove();
    appendChatMessage("Не удалось подготовить ответ. Попробуйте отправить вопрос ещё раз.", "assistant");
  } finally {
    state.chatting = false;
    $("send-chat").disabled = false;
  }
}

function csvCell(value) {
  let text = String(value);
  // Protect spreadsheet users from formula interpretation of future API strings.
  if (/^[\s]*[=+@-]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

function buildOrderCSV(products) {
  const rows = [["SKU", "Товар", "Поставщик", "Рекомендованное количество", "Единица", "Срочность"], ...products.map((p) => [p.sku, p.name, p.supplier, p.recommended_qty, p.unit, URGENCY[p.urgency]])];
  // UTF-8 BOM preserves Cyrillic in Excel; semicolon suits Russian locales.
  return "\uFEFF" + rows.map((row) => row.map(csvCell).join(";")).join("\r\n");
}

function exportOrder() {
  const products = applyFilters().filter((p) => p.recommended_qty > 0);
  if (!products.length) return showNotification("Нет данных для экспорта", "error");
  // Replace with GET /api/export with the same filter parameters in production.
  const url = URL.createObjectURL(new Blob([buildOrderCSV(products)], { type: "text/csv;charset=utf-8;" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "zakupai_order.csv";
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  $("step-review").classList.remove("current");
  $("step-export").classList.add("current");
  showNotification(`Заказ сформирован: ${products.length} позиций`);
}

$("choose-file").addEventListener("click", () => $("file-input").click());
$("file-input").addEventListener("change", (event) => handleFileSelect(event.target.files[0]));
for (const eventName of ["dragenter", "dragover"]) {
  $("drop-zone").addEventListener(eventName, (event) => {
    event.preventDefault();
    if (!state.calculating) $("drop-zone").classList.add("drag-over");
  });
}
$("drop-zone").addEventListener("dragleave", (event) => {
  if (!$("drop-zone").contains(event.relatedTarget)) $("drop-zone").classList.remove("drag-over");
});
$("drop-zone").addEventListener("drop", (event) => {
  event.preventDefault();
  $("drop-zone").classList.remove("drag-over");
  if (state.calculating) return;
  if (event.dataTransfer.files.length !== 1) return showNotification("Выберите один Excel-файл", "error");
  handleFileSelect(event.dataTransfer.files[0]);
});
// Prevent accidental navigation when a file is dropped outside the upload area.
for (const eventName of ["dragover", "drop"]) document.addEventListener(eventName, (event) => event.preventDefault());
$("calculate").addEventListener("click", calculateRecommendations);
$("export").addEventListener("click", exportOrder);
$("search").addEventListener("input", renderRecommendations);
$("supplier-filter").addEventListener("change", renderRecommendations);
$("urgency-filter").addEventListener("change", renderRecommendations);
$("reset-filters").addEventListener("click", resetFilters);
$("recommendation-rows").addEventListener("click", (event) => {
  const button = event.target.closest("[data-sku]");
  if (button) openProductDetails(button.dataset.sku);
});
$("close-dialog").addEventListener("click", () => $("product-dialog").close());
$("product-dialog").addEventListener("click", (event) => {
  const rect = $("product-dialog").getBoundingClientRect();
  if (event.target === $("product-dialog") && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) $("product-dialog").close();
});
$("chat-form").addEventListener("submit", sendChatMessage);
document.querySelectorAll("[data-question]").forEach((button) => button.addEventListener("click", () => {
  $("chat-input").value = button.dataset.question;
  $("chat-input").focus();
}));
document.querySelectorAll(".nav-link").forEach((link) => link.addEventListener("click", () => {
  document.querySelectorAll(".nav-link").forEach((item) => {
    item.classList.toggle("active", item === link);
    if (item === link) item.setAttribute("aria-current", "location");
    else item.removeAttribute("aria-current");
  });
}));
populateSupplierFilter();
updateStatistics();
renderRecommendations();
