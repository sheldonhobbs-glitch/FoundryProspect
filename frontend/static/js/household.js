function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function fmtMoney(value) {
  return `$${Number(value).toFixed(2)}`;
}

// Suggested categories, shared by bills and subscriptions. This is a
// <datalist> (see below), not a fixed enum — typing anything else is
// still fine, these are just the common ones offered as autocomplete.
const CATEGORY_OPTIONS = [
  "bills", "subscriptions", "groceries", "insurance", "rego", "streaming",
  "gym", "eating out", "utilities", "rent/mortgage", "phone/internet",
  "transport/fuel", "healthcare", "home maintenance", "entertainment", "other",
];

const categoryDatalist = document.createElement("datalist");
categoryDatalist.id = "category-options";
for (const category of CATEGORY_OPTIONS) {
  const option = document.createElement("option");
  option.value = category;
  categoryDatalist.appendChild(option);
}
document.body.appendChild(categoryDatalist);

const RESOURCES = {
  bills: {
    label: "Bills",
    endpoint: "/api/bills",
    fields: [
      { name: "name", label: "Name", type: "text", required: true },
      { name: "amount", label: "Amount", type: "number", step: "0.01", required: true },
      { name: "due_date", label: "Due date", type: "date", required: true },
      {
        name: "recurrence", label: "Recurrence", type: "select",
        options: ["one_time", "weekly", "monthly", "quarterly", "yearly"], default: "one_time",
      },
      { name: "category", label: "Category", type: "combo", required: true },
      { name: "notes", label: "Notes", type: "textarea" },
    ],
    renderCard(item) {
      const paidBadge = item.paid ? " · ✅ paid" : "";
      return `<strong>${escapeHtml(item.name)}</strong> — ${fmtMoney(item.amount)}<br>
        due ${item.due_date} · ${escapeHtml(item.category)} · ${item.recurrence.replace("_", " ")}${paidBadge}`;
    },
    actions(item, refresh) {
      const actions = [];
      if (!item.paid) {
        actions.push({
          label: "Mark paid",
          onClick: () => api(`/api/bills/${item.id}/mark-paid`, "POST").then(refresh),
        });
      }
      return actions;
    },
    count(items) {
      const unpaid = items.filter((i) => !i.paid).length;
      return items.length === 0 ? "" : unpaid === 0 ? "all paid" : `${unpaid} unpaid`;
    },
  },
  subscriptions: {
    label: "Subscriptions",
    endpoint: "/api/subscriptions",
    fields: [
      { name: "name", label: "Name", type: "text", required: true },
      { name: "cost", label: "Cost", type: "number", step: "0.01", required: true },
      {
        name: "billing_cycle", label: "Billing cycle", type: "select",
        options: ["weekly", "monthly", "quarterly", "yearly"], default: "monthly",
      },
      { name: "renewal_date", label: "Renewal date", type: "date", required: true },
      { name: "cancel_by_date", label: "Cancel-by date (optional)", type: "date" },
      { name: "category", label: "Category", type: "combo", required: true },
      { name: "notes", label: "Notes", type: "textarea" },
    ],
    renderCard(item) {
      const inactive = item.active ? "" : " · inactive";
      const cancelBy = item.cancel_by_date ? ` · cancel by ${item.cancel_by_date}` : "";
      return `<strong>${escapeHtml(item.name)}</strong> — ${fmtMoney(item.cost)}/${item.billing_cycle}<br>
        renews ${item.renewal_date} · ${escapeHtml(item.category)}${cancelBy}${inactive}`;
    },
    actions(item, refresh) {
      return [
        { label: "Renew", onClick: () => api(`/api/subscriptions/${item.id}/renew`, "POST").then(refresh) },
        {
          label: item.active ? "Deactivate" : "Reactivate",
          onClick: () =>
            api(`/api/subscriptions/${item.id}`, "PATCH", { active: !item.active }).then(refresh),
        },
      ];
    },
    count(items) {
      const active = items.filter((i) => i.active).length;
      return items.length === 0 ? "" : `${active} active`;
    },
  },
  maintenance: {
    label: "Maintenance",
    endpoint: "/api/maintenance",
    fields: [
      { name: "task", label: "Task", type: "text", required: true },
      { name: "property_or_appliance", label: "Property / appliance", type: "text", required: true },
      { name: "last_done", label: "Last done (optional)", type: "date" },
      { name: "next_due", label: "Next due (optional)", type: "date" },
      {
        name: "recurrence_value", label: "Repeats every (optional — leave blank for one-off)",
        type: "number", min: "1",
      },
      {
        name: "recurrence_unit", label: "Repeat unit", type: "select",
        options: ["", "days", "weeks", "months", "years"], default: "",
      },
      { name: "notes", label: "Notes", type: "textarea" },
    ],
    renderCard(item) {
      const repeats = item.recurrence_value && item.recurrence_unit
        ? ` · repeats every ${item.recurrence_value} ${item.recurrence_unit}`
        : "";
      return `<strong>${escapeHtml(item.task)}</strong> (${escapeHtml(item.property_or_appliance)})<br>
        last done ${item.last_done ?? "never"} · next due ${item.next_due ?? "—"}${repeats}`;
    },
    actions(item, refresh) {
      return [
        { label: "Mark done", onClick: () => api(`/api/maintenance/${item.id}/mark-done`, "POST").then(refresh) },
      ];
    },
    count(items) {
      return items.length === 0 ? "" : `${items.length} item${items.length === 1 ? "" : "s"}`;
    },
  },
};

async function api(path, method = "GET", body) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${method} ${path} failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

// --- Identity: "who's using the app right now" (Sheldon/Partner), stored
// in a cookie separate from the real session — pure attribution, not auth.
const IDENTITY_NAMES = { sheldon: "Sheldon", partner: "Partner" };

function applyIdentity(name) {
  window.currentIdentity = name;
  const avatar = document.getElementById("identity-avatar");
  const label = document.getElementById("identity-label");
  if (!name) return;
  avatar.textContent = name === "sheldon" ? "S" : "P";
  avatar.className = `identity-avatar ${name}`;
  label.textContent = IDENTITY_NAMES[name];
}
window.applyIdentity = applyIdentity;

document.querySelectorAll(".identity-option").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const name = btn.dataset.name;
    await api("/api/auth/identity", "POST", { name });
    applyIdentity(name);
    window.showMain();
  });
});

document.getElementById("identity-btn").addEventListener("click", async () => {
  const other = window.currentIdentity === "sheldon" ? "partner" : "sheldon";
  await api("/api/auth/identity", "POST", { name: other });
  applyIdentity(other);
  if (!homeView.hidden) loadDashboard();
});

// --- Navigation: three views —
// home: a curated "what needs you today" digest (the default landing view)
// browse: the section-tile grid, for looking at everything in a category
// detail: one section at a time, opened from browse and closed back to it
// Sections render INTO detail-body and replace whatever was there before —
// nothing accumulates. ---

const homeView = document.getElementById("home-view");
const browseView = document.getElementById("browse-view");
const detailView = document.getElementById("detail-view");
const detailTitle = document.getElementById("detail-title");
const detailBody = document.getElementById("detail-body");
const backBtn = document.getElementById("back-btn");
const notificationsList = document.getElementById("notifications-list");
const composerBar = document.getElementById("composer-bar");
const brandBtn = document.getElementById("brand-btn");
const browseBtn = document.getElementById("browse-btn");

function showDetail(title) {
  homeView.hidden = true;
  browseView.hidden = true;
  detailView.hidden = false;
  composerBar.hidden = true;
  detailTitle.textContent = title;
  detailBody.innerHTML = "";
  window.scrollTo(0, 0);
}

function showBrowse() {
  detailView.hidden = true;
  homeView.hidden = true;
  browseView.hidden = false;
  composerBar.hidden = true;
  refreshHomeCounts();
  window.scrollTo(0, 0);
}

function showHome() {
  detailView.hidden = true;
  browseView.hidden = true;
  homeView.hidden = false;
  composerBar.hidden = false;
  loadNotifications();
  loadDashboard();
  window.scrollTo(0, 0);
}

backBtn.addEventListener("click", showBrowse);
brandBtn.addEventListener("click", showHome);
browseBtn.addEventListener("click", showBrowse);

const SECTION_OPENERS = {
  calendar: () => openCalendar(),
  decisions: () => openDecisions(),
  household: () => (window.openHousehold ? openHousehold() : showDetail("Household")),
  financial: () => (window.openFinancial ? openFinancial() : showDetail("Financial")),
  meals: () => (window.openMeals ? openMeals() : showDetail("Meal planning")),
};

document.querySelectorAll(".section-tile").forEach((btn) => {
  btn.addEventListener("click", () => {
    const key = btn.dataset.resource;
    (SECTION_OPENERS[key] || (() => openResource(key)))();
  });
});

async function refreshHomeCounts() {
  const decisionsEl = document.querySelector('[data-count-for="decisions"]');
  if (decisionsEl) {
    try {
      const items = await api("/api/decisions");
      const open = items.filter((i) => i.status === "open").length;
      decisionsEl.textContent = items.length === 0 ? "" : open === 0 ? "all decided" : `${open} open`;
    } catch {
      decisionsEl.textContent = "";
    }
  }

  const calEl = document.querySelector('[data-count-for="calendar"]');
  if (calEl) {
    try {
      const events = await api("/api/calendar/events");
      calEl.textContent = events.length === 0 ? "" : `${events.length} upcoming`;
    } catch {
      calEl.textContent = "";
    }
  }

  const householdEl = document.querySelector('[data-count-for="household"]');
  if (householdEl) {
    try {
      const [bills, subscriptions, maintenance] = await Promise.all([
        api("/api/bills"), api("/api/subscriptions"), api("/api/maintenance"),
      ]);
      const today = todayStr();
      const dueCount = bills.filter((b) => !b.paid && b.due_date <= today).length
        + subscriptions.filter((s) => s.active && s.renewal_date <= today).length
        + maintenance.filter((m) => m.next_due && m.next_due <= today).length;
      householdEl.textContent = dueCount === 0 ? "all caught up" : `${dueCount} due soon`;
    } catch {
      householdEl.textContent = "";
    }
  }

  if (window.refreshFinancialCount) window.refreshFinancialCount();
  if (window.refreshMealsCount) window.refreshMealsCount();
}

function buildForm(resourceKey, existing, onDone) {
  const config = RESOURCES[resourceKey];
  const form = document.createElement("form");
  form.className = "resource-form";

  for (const field of config.fields) {
    const label = document.createElement("label");
    label.textContent = field.label;
    form.appendChild(label);

    let input;
    if (field.type === "select") {
      input = document.createElement("select");
      for (const opt of field.options) {
        const o = document.createElement("option");
        o.value = opt;
        o.textContent = opt === "" ? "— none, one-off —" : opt.replace("_", " ");
        input.appendChild(o);
      }
    } else if (field.type === "textarea") {
      input = document.createElement("textarea");
    } else if (field.type === "combo") {
      input = document.createElement("input");
      input.type = "text";
      input.setAttribute("list", "category-options");
    } else {
      input = document.createElement("input");
      input.type = field.type;
      if (field.step) input.step = field.step;
      if (field.min) input.min = field.min;
    }
    input.name = field.name;
    if (field.required) input.required = true;
    const existingValue = existing ? existing[field.name] : undefined;
    input.value = existingValue ?? field.default ?? "";
    form.appendChild(input);
  }

  const submitBtn = document.createElement("button");
  submitBtn.type = "submit";
  submitBtn.textContent = existing ? "Save changes" : "Add";
  form.appendChild(submitBtn);

  if (existing) {
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "danger-btn";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", async () => {
      if (!confirm(`Delete "${existing.name || existing.task || existing.item}"?`)) return;
      await api(`${config.endpoint}/${existing.id}`, "DELETE");
      onDone();
    });
    form.appendChild(deleteBtn);
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    for (const field of config.fields) {
      if (data[field.name] === "") data[field.name] = null;
    }
    try {
      if (existing) {
        await api(`${config.endpoint}/${existing.id}`, "PATCH", data);
      } else {
        await api(config.endpoint, "POST", data);
      }
      onDone();
    } catch (err) {
      alert(err.message);
    }
  });

  return form;
}

async function openResource(resourceKey) {
  const config = RESOURCES[resourceKey];
  showDetail(config.label);

  const listEl = document.createElement("div");
  detailBody.appendChild(listEl);

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "add-btn";
  addBtn.textContent = `+ Add ${config.label.toLowerCase().replace(/s$/, "")}`;
  detailBody.appendChild(addBtn);

  async function refresh() {
    const items = await api(config.endpoint);
    listEl.innerHTML = "";
    if (items.length === 0) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Nothing here yet.";
      listEl.appendChild(empty);
    }
    for (const item of items) {
      const card = document.createElement("div");
      card.className = "resource-card";
      card.innerHTML = config.renderCard(item);

      const btnRow = document.createElement("div");
      btnRow.className = "card-actions";

      for (const action of config.actions(item, refresh)) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = action.label;
        btn.addEventListener("click", () => action.onClick().catch((err) => alert(err.message)));
        btnRow.appendChild(btn);
      }

      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.textContent = "Edit";
      editBtn.addEventListener("click", () => {
        const existingForm = card.querySelector("form");
        if (existingForm) {
          existingForm.remove();
          return;
        }
        card.appendChild(buildForm(resourceKey, item, refresh));
      });
      btnRow.appendChild(editBtn);

      card.appendChild(btnRow);
      listEl.appendChild(card);
    }
  }

  addBtn.addEventListener("click", () => {
    const existingForm = detailBody.querySelector(".resource-form:not(.resource-card .resource-form)");
    if (existingForm) {
      existingForm.remove();
      return;
    }
    const form = buildForm(resourceKey, null, () => {
      form.remove();
      refresh();
    });
    detailBody.insertBefore(form, addBtn);
  });

  await refresh();
}

// --- Household: Bills, Subscriptions, Maintenance unified into one
// tabbed screen with a summary strip and a single add button. ---

function buildStripTag(value, label, warn) {
  const tag = document.createElement("div");
  tag.className = "strip-tag" + (warn ? " warn" : "");
  tag.innerHTML = `<div class="st-val">${escapeHtml(String(value))}</div><div class="st-label">${escapeHtml(label)}</div>`;
  return tag;
}

const HOUSEHOLD_TABS = ["bills", "subscriptions", "maintenance"];

async function openHousehold() {
  showDetail("Household");
  let currentTab = "bills";

  const summaryRow = document.createElement("div");
  summaryRow.className = "summary-strip";
  detailBody.appendChild(summaryRow);

  const tabsRow = document.createElement("div");
  tabsRow.className = "tabs";
  detailBody.appendChild(tabsRow);

  const tabContent = document.createElement("div");
  detailBody.appendChild(tabContent);

  const fab = document.createElement("button");
  fab.type = "button";
  fab.className = "fab";
  fab.textContent = "+";
  detailBody.appendChild(fab);

  async function refreshSummary() {
    const [bills, subscriptions, maintenance] = await Promise.all([
      api("/api/bills"), api("/api/subscriptions"), api("/api/maintenance"),
    ]);
    const today = todayStr();
    const dueSoon = bills.filter((b) => !b.paid && b.due_date <= today).length
      + maintenance.filter((m) => m.next_due && m.next_due <= today).length;
    const activeSubs = subscriptions.filter((s) => s.active).length;
    const overdueMaint = maintenance.filter((m) => m.next_due && m.next_due < today).length;
    summaryRow.innerHTML = "";
    summaryRow.appendChild(buildStripTag(dueSoon, "Due soon", dueSoon > 0));
    summaryRow.appendChild(buildStripTag(activeSubs, "Subs", false));
    summaryRow.appendChild(buildStripTag(overdueMaint, "Overdue", overdueMaint > 0));
  }

  async function renderTab() {
    tabContent.innerHTML = "";
    const config = RESOURCES[currentTab];
    const items = await api(config.endpoint);
    if (items.length === 0) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Nothing here yet.";
      tabContent.appendChild(empty);
    }
    for (const item of items) {
      const card = document.createElement("div");
      card.className = "resource-card";
      card.innerHTML = config.renderCard(item);

      const btnRow = document.createElement("div");
      btnRow.className = "card-actions";
      for (const action of config.actions(item, () => { renderTab(); refreshSummary(); })) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = action.label;
        btn.addEventListener("click", () => action.onClick().catch((err) => alert(err.message)));
        btnRow.appendChild(btn);
      }
      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.textContent = "Edit";
      editBtn.addEventListener("click", () => {
        const existingForm = card.querySelector("form");
        if (existingForm) {
          existingForm.remove();
          return;
        }
        card.appendChild(buildForm(currentTab, item, () => { renderTab(); refreshSummary(); }));
      });
      btnRow.appendChild(editBtn);
      card.appendChild(btnRow);
      tabContent.appendChild(card);
    }
  }

  for (const key of HOUSEHOLD_TABS) {
    const tab = document.createElement("div");
    tab.className = "tab" + (key === currentTab ? " active" : "");
    tab.textContent = RESOURCES[key].label;
    tab.dataset.tab = key;
    tab.addEventListener("click", () => {
      currentTab = key;
      tabsRow.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === key));
      renderTab();
    });
    tabsRow.appendChild(tab);
  }

  fab.addEventListener("click", () => {
    const existingForm = tabContent.querySelector(":scope > .resource-form");
    if (existingForm) {
      existingForm.remove();
      return;
    }
    const form = buildForm(currentTab, null, () => {
      form.remove();
      renderTab();
      refreshSummary();
    });
    tabContent.insertBefore(form, tabContent.firstChild);
  });

  await refreshSummary();
  await renderTab();
}
window.openHousehold = openHousehold;

function localInputToIso(value) {
  return new Date(value).toISOString();
}

function isoToLocalInput(iso) {
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const OWNER_LABELS = { sheldon: "Sheldon", partner: "Partner", shared: "shared" };

function renderEventCard(event) {
  const start = new Date(event.start_time);
  const end = new Date(event.end_time);
  const fmt = event.all_day
    ? "All day"
    : `${start.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}` +
      ` – ${end.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
  const loc = event.location ? ` · ${escapeHtml(event.location)}` : "";
  const owner = event.owner || "shared";
  return `<div class="event-row-inner">
      <div class="event-time">${fmt}</div>
      <div style="flex:1"><strong>${escapeHtml(event.title)}</strong>${loc ? `<div class="muted">${loc.replace(" · ", "")}</div>` : ""}</div>
      <span class="owner-pill ${owner}">${escapeHtml(OWNER_LABELS[owner] || owner)}</span>
    </div>`;
}

function getWeekDays(anchor) {
  const day = anchor.getDay(); // 0=Sun..6=Sat
  const mondayOffset = day === 0 ? -6 : 1 - day;
  const monday = new Date(anchor);
  monday.setDate(anchor.getDate() + mondayOffset);
  monday.setHours(0, 0, 0, 0);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d;
  });
}

function dateKey(d) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function buildEventForm(existing, defaultOwner, onDone) {
  const form = document.createElement("form");
  form.className = "resource-form";
  let selectedOwner = existing ? existing.owner || "shared" : defaultOwner || "shared";

  const fields = [
    { name: "title", label: "Title", type: "text", required: true },
    { name: "start_time", label: "Start", type: "datetime-local", required: true },
    { name: "end_time", label: "End", type: "datetime-local", required: true },
    { name: "all_day", label: "All day", type: "checkbox" },
    { name: "location", label: "Location (optional)", type: "text" },
    { name: "description", label: "Description (optional)", type: "textarea" },
  ];

  for (const field of fields) {
    const label = document.createElement("label");
    label.textContent = field.label;
    form.appendChild(label);

    const input = document.createElement(field.type === "textarea" ? "textarea" : "input");
    if (field.type !== "textarea") input.type = field.type;
    input.name = field.name;
    if (field.required) input.required = true;

    if (field.type === "checkbox") {
      input.checked = existing ? existing.all_day : false;
    } else if (field.type === "datetime-local") {
      input.value = existing ? isoToLocalInput(existing[field.name]) : "";
    } else {
      input.value = existing ? existing[field.name] ?? "" : "";
    }
    form.appendChild(input);
  }

  const ownerLabel = document.createElement("label");
  ownerLabel.textContent = "Whose calendar";
  form.appendChild(ownerLabel);
  const toggleRow = document.createElement("div");
  toggleRow.className = "toggle-row";
  for (const key of ["shared", "sheldon", "partner"]) {
    const chip = document.createElement("div");
    chip.className = "toggle-chip" + (selectedOwner === key ? " on" : "");
    chip.textContent = OWNER_LABELS[key];
    chip.addEventListener("click", () => {
      selectedOwner = key;
      toggleRow.querySelectorAll(".toggle-chip").forEach((c) => c.classList.remove("on"));
      chip.classList.add("on");
    });
    toggleRow.appendChild(chip);
  }
  form.appendChild(toggleRow);

  const submitBtn = document.createElement("button");
  submitBtn.type = "submit";
  submitBtn.textContent = existing ? "Save changes" : "Add";
  form.appendChild(submitBtn);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(form);
    const payload = {
      title: formData.get("title"),
      start_time: localInputToIso(formData.get("start_time")),
      end_time: localInputToIso(formData.get("end_time")),
      all_day: formData.get("all_day") === "on",
      location: formData.get("location") || null,
      description: formData.get("description") || null,
      owner: selectedOwner,
    };
    try {
      if (existing) {
        await api(`/api/calendar/events/${existing.id}`, "PATCH", payload);
      } else {
        await api("/api/calendar/events", "POST", payload);
      }
      onDone();
    } catch (err) {
      alert(err.message);
    }
  });

  return form;
}

async function openCalendar() {
  showDetail("Calendar");

  const status = await api("/api/calendar/status").catch(() => null);
  if (!status) {
    detailBody.innerHTML = '<p class="muted">Could not reach the calendar API.</p>';
    return;
  }
  if (!status.configured) {
    detailBody.innerHTML =
      '<p class="muted">Google Calendar isn\'t set up yet — add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env first.</p>';
    return;
  }
  if (!status.connected) {
    const connectLink = document.createElement("a");
    connectLink.href = "/api/calendar/connect";
    connectLink.className = "add-btn";
    connectLink.style.display = "block";
    connectLink.style.textAlign = "center";
    connectLink.textContent = "Connect Google Calendar";
    detailBody.appendChild(connectLink);
    return;
  }

  const infoRow = document.createElement("div");
  infoRow.className = "muted";
  infoRow.textContent = status.google_account_email
    ? `Connected as ${status.google_account_email}`
    : "Connected";
  detailBody.appendChild(infoRow);

  const toolbarRow = document.createElement("div");
  toolbarRow.className = "card-actions";
  const syncBtn = document.createElement("button");
  syncBtn.type = "button";
  syncBtn.textContent = "Sync now";
  const disconnectBtn = document.createElement("button");
  disconnectBtn.type = "button";
  disconnectBtn.textContent = "Disconnect";
  toolbarRow.appendChild(syncBtn);
  toolbarRow.appendChild(disconnectBtn);
  detailBody.appendChild(toolbarRow);

  const today = new Date();
  const weekDays = getWeekDays(today);
  let selectedDay = dateKey(today);

  const dayTabsRow = document.createElement("div");
  dayTabsRow.className = "day-tabs";
  detailBody.appendChild(dayTabsRow);

  const dayLabel = document.createElement("div");
  dayLabel.className = "section-label";
  detailBody.appendChild(dayLabel);

  const listEl = document.createElement("div");
  detailBody.appendChild(listEl);

  const fab = document.createElement("button");
  fab.type = "button";
  fab.className = "fab";
  fab.textContent = "+";
  detailBody.appendChild(fab);

  let allEvents = [];

  function renderDayTabs() {
    dayTabsRow.innerHTML = "";
    for (const d of weekDays) {
      const key = dateKey(d);
      const tab = document.createElement("div");
      tab.className = "day-tab" + (key === selectedDay ? " active" : "");
      tab.innerHTML = `<div class="dt-name">${d.toLocaleDateString(undefined, { weekday: "short" })}</div><div class="dt-num">${d.getDate()}</div>`;
      tab.addEventListener("click", () => {
        selectedDay = key;
        renderDayTabs();
        renderDayEvents();
      });
      dayTabsRow.appendChild(tab);
    }
  }

  function renderEventActions(event, card, refresh) {
    const btnRow = document.createElement("div");
    btnRow.className = "card-actions";

    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.textContent = "Edit";
    editBtn.addEventListener("click", () => {
      const existingForm = card.querySelector("form");
      if (existingForm) {
        existingForm.remove();
        return;
      }
      card.appendChild(buildEventForm(event, event.owner, refresh));
    });
    btnRow.appendChild(editBtn);

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", async () => {
      if (!confirm(`Delete "${event.title}"?`)) return;
      await api(`/api/calendar/events/${event.id}`, "DELETE");
      refresh();
    });
    btnRow.appendChild(deleteBtn);

    card.appendChild(btnRow);
  }

  function renderDayEvents() {
    const d = weekDays.find((wd) => dateKey(wd) === selectedDay) || today;
    dayLabel.textContent = d.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });

    const dayEvents = allEvents.filter((e) => dateKey(new Date(e.start_time)) === selectedDay);
    listEl.innerHTML = "";
    if (dayEvents.length === 0) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Nothing on this day.";
      listEl.appendChild(empty);
      return;
    }
    for (const event of dayEvents) {
      const card = document.createElement("div");
      card.className = `event-row ${event.owner || "shared"}`;
      card.innerHTML = renderEventCard(event);
      renderEventActions(event, card, refresh);
      listEl.appendChild(card);
    }
  }

  async function refresh() {
    allEvents = await api("/api/calendar/events");
    renderDayEvents();
  }

  syncBtn.addEventListener("click", async () => {
    syncBtn.disabled = true;
    syncBtn.textContent = "Syncing…";
    try {
      await api("/api/calendar/sync", "POST");
      await refresh();
    } catch (err) {
      alert(err.message);
    } finally {
      syncBtn.disabled = false;
      syncBtn.textContent = "Sync now";
    }
  });

  disconnectBtn.addEventListener("click", async () => {
    if (!confirm("Disconnect Google Calendar?")) return;
    await api("/api/calendar/disconnect", "POST");
    openCalendar();
  });

  fab.addEventListener("click", () => {
    const existingForm = detailBody.querySelector(".resource-form");
    if (existingForm) {
      existingForm.remove();
      return;
    }
    const form = buildEventForm(null, "shared", () => {
      form.remove();
      refresh();
    });
    detailBody.insertBefore(form, fab);
  });

  renderDayTabs();
  await refresh();
}

// --- Decisions: multi-option voting. Both people vote from their own
// identity; a decision resolves automatically when both pick the same
// option, and stays open (showing "you disagree") otherwise. ---

function decisionStatusText(decision) {
  const votes = {};
  for (const v of decision.votes) votes[v.voter] = v.option_id;
  if (decision.status === "decided") {
    return `Both voted ${decision.decision} · locked in`;
  }
  const voted = Object.keys(votes);
  if (voted.length === 0) return "No votes yet";
  if (voted.length === 1) {
    const waitingOn = voted[0] === "sheldon" ? "Partner" : "Sheldon";
    return `${IDENTITY_NAMES[voted[0]]} voted · awaiting ${waitingOn}`;
  }
  return "You disagree — needs a conversation, not a tiebreaker";
}

function buildDecisionCard(decision, refresh) {
  const card = document.createElement("div");
  card.className = "decision-card";

  const top = document.createElement("div");
  top.className = "dc-top";
  const title = document.createElement("div");
  title.className = "dc-title";
  title.textContent = decision.item;
  const pill = document.createElement("span");
  pill.className = `status-pill ${decision.status === "decided" ? "resolved" : "open"}`;
  pill.textContent = decision.status === "decided" ? "resolved" : "open";
  top.appendChild(title);
  top.appendChild(pill);
  card.appendChild(top);

  const votesByVoter = {};
  for (const v of decision.votes) votesByVoter[v.voter] = v.option_id;

  const avatarsRow = document.createElement("div");
  avatarsRow.className = "vote-avatars";
  for (const name of Object.keys(IDENTITY_NAMES)) {
    const av = document.createElement("div");
    av.className = `v-avatar ${name in votesByVoter ? name : "pending"}`;
    av.textContent = name === "sheldon" ? "S" : "P";
    avatarsRow.appendChild(av);
  }
  card.appendChild(avatarsRow);

  const statusText = document.createElement("div");
  statusText.className = "dc-status-text";
  statusText.textContent = decisionStatusText(decision);
  card.appendChild(statusText);

  if (decision.notes) {
    const notesEl = document.createElement("div");
    notesEl.className = "muted";
    notesEl.style.marginTop = "6px";
    notesEl.textContent = decision.notes;
    card.appendChild(notesEl);
  }

  const optionsWrap = document.createElement("div");
  optionsWrap.hidden = true;
  optionsWrap.style.marginTop = "10px";

  for (const option of decision.options) {
    const row = document.createElement("div");
    row.className = "option-row";
    const isMyVote = votesByVoter[window.currentIdentity] === option.id;
    const isWinner = decision.status === "decided" && decision.decision === option.text;
    if (isWinner) row.classList.add("resolved-winner");
    else if (isMyVote) row.classList.add("my-vote");

    const optTitle = document.createElement("div");
    optTitle.className = "opt-title";
    optTitle.textContent = option.text;
    row.appendChild(optTitle);

    const votersRow = document.createElement("div");
    votersRow.className = "opt-voters";
    for (const [voter, optId] of Object.entries(votesByVoter)) {
      if (optId !== option.id) continue;
      const av = document.createElement("div");
      av.className = `v-avatar ${voter}`;
      av.textContent = voter === "sheldon" ? "S" : "P";
      votersRow.appendChild(av);
    }
    row.appendChild(votersRow);

    row.addEventListener("click", async (e) => {
      e.stopPropagation();
      try {
        await api(`/api/decisions/${decision.id}/vote`, "POST", { option_id: option.id });
        refresh();
      } catch (err) {
        alert(err.message);
      }
    });
    optionsWrap.appendChild(row);
  }

  const utilityRow = document.createElement("div");
  utilityRow.className = "card-actions";
  if (decision.status === "decided") {
    const reopenBtn = document.createElement("button");
    reopenBtn.type = "button";
    reopenBtn.textContent = "Reopen for a new vote";
    reopenBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm("Reopen this decision? Existing votes will be cleared.")) return;
      await api(`/api/decisions/${decision.id}/reopen`, "POST");
      refresh();
    });
    utilityRow.appendChild(reopenBtn);
  }
  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.textContent = "Delete";
  deleteBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    if (!confirm(`Delete "${decision.item}"?`)) return;
    await api(`/api/decisions/${decision.id}`, "DELETE");
    refresh();
  });
  utilityRow.appendChild(deleteBtn);
  optionsWrap.appendChild(utilityRow);

  card.appendChild(optionsWrap);
  card.addEventListener("click", () => {
    optionsWrap.hidden = !optionsWrap.hidden;
  });

  return card;
}

function buildNewDecisionForm(onDone) {
  const form = document.createElement("form");
  form.className = "resource-form";

  const questionLabel = document.createElement("label");
  questionLabel.textContent = "Question";
  form.appendChild(questionLabel);
  const questionInput = document.createElement("textarea");
  questionInput.name = "item";
  questionInput.required = true;
  form.appendChild(questionInput);

  const optionsLabel = document.createElement("label");
  optionsLabel.textContent = "Options";
  form.appendChild(optionsLabel);
  const optionsWrap = document.createElement("div");
  form.appendChild(optionsWrap);

  function addOptionInput(placeholder) {
    const input = document.createElement("input");
    input.type = "text";
    input.name = "option";
    input.placeholder = placeholder;
    input.required = true;
    optionsWrap.appendChild(input);
  }
  addOptionInput("Option 1");
  addOptionInput("Option 2");

  const addOptionBtn = document.createElement("div");
  addOptionBtn.className = "add-btn";
  addOptionBtn.textContent = "+ Add another option";
  addOptionBtn.addEventListener("click", () => addOptionInput(`Option ${optionsWrap.children.length + 1}`));
  form.appendChild(addOptionBtn);

  const submitBtn = document.createElement("button");
  submitBtn.type = "submit";
  submitBtn.textContent = "Create decision";
  form.appendChild(submitBtn);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const item = questionInput.value.trim();
    const options = Array.from(optionsWrap.querySelectorAll('input[name="option"]'))
      .map((i) => i.value.trim())
      .filter(Boolean);
    if (!item || options.length < 2) {
      alert("Add a question and at least two options.");
      return;
    }
    try {
      await api("/api/decisions", "POST", { item, options });
      onDone();
    } catch (err) {
      alert(err.message);
    }
  });

  return form;
}

async function openDecisions() {
  showDetail("Decisions");

  const listEl = document.createElement("div");
  detailBody.appendChild(listEl);

  const fab = document.createElement("button");
  fab.type = "button";
  fab.className = "fab";
  fab.textContent = "+";
  detailBody.appendChild(fab);

  async function refresh() {
    const decisions = await api("/api/decisions");
    listEl.innerHTML = "";
    if (decisions.length === 0) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "No decisions yet.";
      listEl.appendChild(empty);
    }
    for (const decision of decisions) {
      listEl.appendChild(buildDecisionCard(decision, refresh));
    }
  }

  fab.addEventListener("click", () => {
    const existingForm = detailBody.querySelector(".resource-form");
    if (existingForm) {
      existingForm.remove();
      return;
    }
    const form = buildNewDecisionForm(() => {
      form.remove();
      refresh();
    });
    detailBody.insertBefore(form, fab);
  });

  await refresh();
}

// --- Financial: manual cashflow, receipts, warranties (with expiry
// tracking). No bank feed — everything here is typed in or (later) scanned. ---

function addDaysStr(dateStr, days) {
  const d = new Date(dateStr + "T00:00:00");
  d.setDate(d.getDate() + days);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function buildQuickAction(icon, label) {
  const btn = document.createElement("div");
  btn.className = "qa-btn";
  btn.innerHTML = `<div class="qa-icon">${icon}</div><div class="qa-label">${escapeHtml(label)}</div>`;
  return btn;
}

function buildSummaryTag(value, label) {
  const tag = document.createElement("div");
  tag.className = "summary-tag";
  tag.innerHTML = `<div class="t-label">${escapeHtml(label)}</div><div class="t-val">${value}</div>`;
  return tag;
}

async function renderFinancialSummary(container, view, onViewChange) {
  const summary = await api(`/api/financial/summary?view=${view}`).catch(() => null);
  container.innerHTML = "";
  if (!summary) {
    container.innerHTML = '<p class="muted">Could not load the financial summary.</p>';
    return;
  }

  const top = document.createElement("div");
  top.className = "summary-top";
  const label = document.createElement("div");
  label.className = "s-label";
  label.textContent = "Cashflow";
  const toggle = document.createElement("div");
  toggle.className = "view-toggle";
  const monthlyBtn = document.createElement("button");
  monthlyBtn.type = "button";
  monthlyBtn.textContent = "This month";
  monthlyBtn.className = view === "monthly" ? "active" : "";
  monthlyBtn.addEventListener("click", () => onViewChange("monthly"));
  const allBtn = document.createElement("button");
  allBtn.type = "button";
  allBtn.textContent = "All time";
  allBtn.className = view === "alltime" ? "active" : "";
  allBtn.addEventListener("click", () => onViewChange("alltime"));
  toggle.appendChild(monthlyBtn);
  toggle.appendChild(allBtn);
  top.appendChild(label);
  top.appendChild(toggle);
  container.appendChild(top);

  const positive = summary.net >= 0;
  const amount = document.createElement("div");
  amount.className = "s-amount " + (positive ? "positive" : "negative");
  amount.textContent = (positive ? "" : "− ") + fmtMoney(Math.abs(summary.net));
  container.appendChild(amount);

  const note = document.createElement("div");
  note.className = "s-note";
  const period = view === "monthly" ? "this month" : "since tracking began";
  note.textContent = `${fmtMoney(summary.income)} in vs ${fmtMoney(summary.expenses)} out ${period}` +
    (positive ? " — you're ahead." : " — you've drawn down.");
  container.appendChild(note);

  const importLink = document.createElement("div");
  importLink.className = "import-income-link";
  importLink.textContent = "📥 Import income (CSV)";
  importLink.addEventListener("click", () => showToast("CSV import isn't wired up yet — coming in a later phase."));
  container.appendChild(importLink);

  const tagsRow = document.createElement("div");
  tagsRow.className = "summary-tags";
  tagsRow.appendChild(buildSummaryTag(summary.receipts_count, "Receipts"));
  tagsRow.appendChild(buildSummaryTag(summary.warranties_count, "Warranties"));
  tagsRow.appendChild(buildSummaryTag(summary.warranties_expiring_count, "Expiring"));
  container.appendChild(tagsRow);
}

function buildReceiptForm(existing, onDone) {
  const form = document.createElement("form");
  form.className = "resource-form";
  const fields = [
    { name: "vendor", label: "Vendor", type: "text", required: true },
    { name: "amount", label: "Amount", type: "number", step: "0.01", required: true },
    { name: "purchased_at", label: "Date", type: "date", required: true },
    { name: "category", label: "Category", type: "combo", required: true },
    { name: "notes", label: "Notes (optional)", type: "textarea" },
  ];
  for (const field of fields) {
    const label = document.createElement("label");
    label.textContent = field.label;
    form.appendChild(label);
    let input;
    if (field.type === "textarea") {
      input = document.createElement("textarea");
    } else if (field.type === "combo") {
      input = document.createElement("input");
      input.type = "text";
      input.setAttribute("list", "category-options");
    } else {
      input = document.createElement("input");
      input.type = field.type;
      if (field.step) input.step = field.step;
    }
    input.name = field.name;
    if (field.required) input.required = true;
    input.value = existing ? existing[field.name] ?? "" : "";
    form.appendChild(input);
  }

  const submitBtn = document.createElement("button");
  submitBtn.type = "submit";
  submitBtn.textContent = existing ? "Save changes" : "Save receipt";
  form.appendChild(submitBtn);

  if (existing) {
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "danger-btn";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", async () => {
      if (!confirm(`Delete this receipt from ${existing.vendor}?`)) return;
      await api(`/api/financial/receipts/${existing.id}`, "DELETE");
      onDone();
    });
    form.appendChild(deleteBtn);
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    if (data.notes === "") data.notes = null;
    try {
      if (existing) {
        await api(`/api/financial/receipts/${existing.id}`, "PATCH", data);
      } else {
        await api("/api/financial/receipts", "POST", data);
      }
      onDone();
    } catch (err) {
      alert(err.message);
    }
  });

  return form;
}

async function buildWarrantyForm(existing, onDone) {
  const form = document.createElement("form");
  form.className = "resource-form";
  const fields = [
    { name: "item", label: "Item", type: "text", required: true },
    { name: "retailer", label: "Retailer (optional)", type: "text" },
    { name: "purchase_date", label: "Purchase date", type: "date", required: true },
    { name: "expiry_date", label: "Expiry date", type: "date", required: true },
    { name: "document_reference", label: "Document reference (optional)", type: "text" },
    { name: "notes", label: "Notes (optional)", type: "textarea" },
  ];
  for (const field of fields) {
    const label = document.createElement("label");
    label.textContent = field.label;
    form.appendChild(label);
    const input = document.createElement(field.type === "textarea" ? "textarea" : "input");
    if (field.type !== "textarea") input.type = field.type;
    input.name = field.name;
    if (field.required) input.required = true;
    input.value = existing ? existing[field.name] ?? "" : "";
    form.appendChild(input);
  }

  const receiptLabel = document.createElement("label");
  receiptLabel.textContent = "Link a receipt (optional) — proof of purchase";
  form.appendChild(receiptLabel);
  const receiptSelect = document.createElement("select");
  receiptSelect.name = "receipt_id";
  const noneOpt = document.createElement("option");
  noneOpt.value = "";
  noneOpt.textContent = "— none —";
  receiptSelect.appendChild(noneOpt);
  const receipts = await api("/api/financial/receipts").catch(() => []);
  for (const r of receipts) {
    const opt = document.createElement("option");
    opt.value = String(r.id);
    opt.textContent = `${r.vendor} — ${fmtMoney(r.amount)} (${r.purchased_at})`;
    if (existing && existing.receipt_id === r.id) opt.selected = true;
    receiptSelect.appendChild(opt);
  }
  form.appendChild(receiptSelect);

  const submitBtn = document.createElement("button");
  submitBtn.type = "submit";
  submitBtn.textContent = existing ? "Save changes" : "Save warranty";
  form.appendChild(submitBtn);

  if (existing) {
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "danger-btn";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", async () => {
      if (!confirm(`Delete "${existing.item}"?`)) return;
      await api(`/api/warranties/${existing.id}`, "DELETE");
      onDone();
    });
    form.appendChild(deleteBtn);
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    for (const key of Object.keys(data)) {
      if (data[key] === "") data[key] = null;
    }
    if (data.receipt_id) data.receipt_id = Number(data.receipt_id);
    try {
      if (existing) {
        await api(`/api/warranties/${existing.id}`, "PATCH", data);
      } else {
        await api("/api/warranties", "POST", data);
      }
      onDone();
    } catch (err) {
      alert(err.message);
    }
  });

  return form;
}

function buildCashflowForm(onDone) {
  const form = document.createElement("form");
  form.className = "resource-form";
  let selectedKind = "income";

  const kindLabel = document.createElement("label");
  kindLabel.textContent = "Type";
  form.appendChild(kindLabel);
  const toggleRow = document.createElement("div");
  toggleRow.className = "toggle-row";
  for (const key of ["income", "expense"]) {
    const chip = document.createElement("div");
    chip.className = "toggle-chip" + (key === selectedKind ? " on" : "");
    chip.textContent = key === "income" ? "Income" : "Expense";
    chip.addEventListener("click", () => {
      selectedKind = key;
      toggleRow.querySelectorAll(".toggle-chip").forEach((c) => c.classList.remove("on"));
      chip.classList.add("on");
    });
    toggleRow.appendChild(chip);
  }
  form.appendChild(toggleRow);

  const fields = [
    { name: "amount", label: "Amount", type: "number", step: "0.01", required: true },
    { name: "entry_date", label: "Date", type: "date", required: true },
    { name: "note", label: "Note (optional)", type: "text" },
  ];
  for (const field of fields) {
    const label = document.createElement("label");
    label.textContent = field.label;
    form.appendChild(label);
    const input = document.createElement("input");
    input.type = field.type;
    if (field.step) input.step = field.step;
    input.name = field.name;
    if (field.required) input.required = true;
    form.appendChild(input);
  }

  const submitBtn = document.createElement("button");
  submitBtn.type = "submit";
  submitBtn.textContent = "Log entry";
  form.appendChild(submitBtn);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(form);
    const payload = {
      kind: selectedKind,
      amount: formData.get("amount"),
      entry_date: formData.get("entry_date"),
      note: formData.get("note") || null,
    };
    try {
      await api("/api/financial/cashflow", "POST", payload);
      onDone();
    } catch (err) {
      alert(err.message);
    }
  });

  return form;
}

async function openFinancial() {
  showDetail("Financial");
  let currentView = "monthly";

  const summaryCard = document.createElement("div");
  summaryCard.className = "summary-card";
  detailBody.appendChild(summaryCard);

  const quickActions = document.createElement("div");
  quickActions.className = "quick-actions";
  const qaReceipt = buildQuickAction("🧾", "Import receipt");
  const qaWarranty = buildQuickAction("🛡️", "Add warranty");
  const qaCashflow = buildQuickAction("💵", "Log income/expense");
  quickActions.appendChild(qaReceipt);
  quickActions.appendChild(qaWarranty);
  quickActions.appendChild(qaCashflow);
  detailBody.appendChild(quickActions);

  const formSlot = document.createElement("div");
  detailBody.appendChild(formSlot);

  const receiptsLabel = document.createElement("div");
  receiptsLabel.className = "section-label";
  receiptsLabel.textContent = "Recent receipts";
  detailBody.appendChild(receiptsLabel);
  const receiptsList = document.createElement("div");
  detailBody.appendChild(receiptsList);

  const warrantiesLabel = document.createElement("div");
  warrantiesLabel.className = "section-label";
  warrantiesLabel.textContent = "Warranties";
  detailBody.appendChild(warrantiesLabel);
  const warrantiesList = document.createElement("div");
  detailBody.appendChild(warrantiesList);

  const importHint = document.createElement("p");
  importHint.className = "muted";
  importHint.style.textAlign = "center";
  importHint.style.marginTop = "8px";
  importHint.textContent = "Manual and CSV entry only — no live bank feed.";
  detailBody.appendChild(importHint);

  function clearFormSlot() {
    formSlot.innerHTML = "";
  }

  async function refreshSummary() {
    await renderFinancialSummary(summaryCard, currentView, (newView) => {
      currentView = newView;
      refreshSummary();
    });
  }

  async function refreshReceipts() {
    const receipts = await api("/api/financial/receipts");
    receiptsList.innerHTML = "";
    if (receipts.length === 0) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "No receipts yet.";
      receiptsList.appendChild(empty);
      return;
    }
    for (const r of receipts.slice(0, 10)) {
      const card = document.createElement("div");
      card.className = "resource-card";
      card.innerHTML = `<strong>${escapeHtml(r.vendor)}</strong> — ${fmtMoney(r.amount)}<br>${r.purchased_at} · ${escapeHtml(r.category)}`;
      const btnRow = document.createElement("div");
      btnRow.className = "card-actions";
      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.textContent = "Edit";
      editBtn.addEventListener("click", () => {
        const existingForm = card.querySelector("form");
        if (existingForm) {
          existingForm.remove();
          return;
        }
        card.appendChild(buildReceiptForm(r, () => { refreshReceipts(); refreshSummary(); }));
      });
      btnRow.appendChild(editBtn);
      card.appendChild(btnRow);
      receiptsList.appendChild(card);
    }
  }

  async function refreshWarranties() {
    const warranties = await api("/api/warranties");
    warrantiesList.innerHTML = "";
    if (warranties.length === 0) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "No warranties yet.";
      warrantiesList.appendChild(empty);
      return;
    }
    const today = todayStr();
    for (const w of warranties) {
      const expiringSoon = w.expiry_date >= today && w.expiry_date <= addDaysStr(today, 30);
      const card = document.createElement("div");
      card.className = "resource-card";
      const retailer = w.retailer ? ` · ${escapeHtml(w.retailer)}` : "";
      const expiryLine = expiringSoon
        ? `<span style="color: var(--coral); font-weight: 500;">Expires ${w.expiry_date}</span>`
        : `Covered until ${w.expiry_date}`;
      card.innerHTML = `<strong>${escapeHtml(w.item)}</strong>${retailer}<br>${expiryLine}`;
      const btnRow = document.createElement("div");
      btnRow.className = "card-actions";
      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.textContent = "Edit";
      editBtn.addEventListener("click", async () => {
        const existingForm = card.querySelector("form");
        if (existingForm) {
          existingForm.remove();
          return;
        }
        card.appendChild(await buildWarrantyForm(w, () => { refreshWarranties(); refreshSummary(); }));
      });
      btnRow.appendChild(editBtn);
      card.appendChild(btnRow);
      warrantiesList.appendChild(card);
    }
  }

  qaReceipt.addEventListener("click", () => {
    clearFormSlot();
    const form = buildReceiptForm(null, () => {
      clearFormSlot();
      refreshReceipts();
      refreshSummary();
    });
    formSlot.appendChild(form);
  });

  qaWarranty.addEventListener("click", async () => {
    clearFormSlot();
    const form = await buildWarrantyForm(null, () => {
      clearFormSlot();
      refreshWarranties();
      refreshSummary();
    });
    formSlot.appendChild(form);
  });

  qaCashflow.addEventListener("click", () => {
    clearFormSlot();
    const form = buildCashflowForm(() => {
      clearFormSlot();
      refreshSummary();
      showToast("Logged");
    });
    formSlot.appendChild(form);
  });

  await refreshSummary();
  await refreshReceipts();
  await refreshWarranties();
}
window.openFinancial = openFinancial;

window.refreshFinancialCount = async function () {
  const el = document.querySelector('[data-count-for="financial"]');
  if (!el) return;
  try {
    const summary = await api("/api/financial/summary?view=monthly");
    el.textContent = summary.warranties_expiring_count > 0
      ? `${summary.warranties_expiring_count} expiring`
      : `${fmtMoney(summary.net)} this month`;
  } catch {
    el.textContent = "";
  }
};

async function loadNotifications() {
  notificationsList.innerHTML = "";
  const notifications = await api("/api/notifications").catch(() => []);
  for (const n of notifications) {
    const bubble = document.createElement("div");
    bubble.className = "bubble system notification-bubble";
    bubble.innerHTML = `💡 ${escapeHtml(n.message)}`;
    const dismissBtn = document.createElement("button");
    dismissBtn.type = "button";
    dismissBtn.textContent = "Dismiss";
    dismissBtn.addEventListener("click", async () => {
      await api(`/api/notifications/${n.id}/dismiss`, "POST");
      bubble.remove();
    });
    bubble.appendChild(dismissBtn);
    notificationsList.appendChild(bubble);
  }
}

// --- Home digest: "what needs you today", curated from every resource
// rather than an unfiltered dump. Actionable items (bills/subscriptions/
// maintenance due) get a tap-to-complete checkbox; calendar events and
// open decisions expand in place for more detail. ---

const toastEl = document.getElementById("toast");
let toastTimer = null;

function showToast(message) {
  toastEl.textContent = message;
  toastEl.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2200);
}

function todayStr() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function renderDigestHeader() {
  const today = new Date();
  document.getElementById("digest-date").textContent = today.toLocaleDateString(undefined, {
    weekday: "long", day: "numeric", month: "long",
  });
  const hour = today.getHours();
  const greeting = hour < 12 ? "Morning." : hour < 18 ? "Afternoon." : "Evening.";
  document.getElementById("digest-greeting").textContent = greeting;
}

function buildFeedCard({ icon, iconClass, title, meta, urgent, checkbox, onCheck, expandHtml }) {
  const card = document.createElement("div");
  card.className = "feed-card" + (expandHtml ? "" : " static");

  const row = document.createElement("div");
  row.className = "feed-row";

  const badge = document.createElement("div");
  badge.className = `icon-badge ${iconClass}`;
  badge.textContent = icon;
  row.appendChild(badge);

  const textWrap = document.createElement("div");
  textWrap.style.flex = "1";
  const titleEl = document.createElement("div");
  titleEl.className = "card-title";
  titleEl.textContent = title;
  const metaEl = document.createElement("div");
  metaEl.className = "card-meta" + (urgent ? " urgent" : "");
  metaEl.textContent = meta;
  textWrap.appendChild(titleEl);
  textWrap.appendChild(metaEl);
  row.appendChild(textWrap);

  if (checkbox) {
    const check = document.createElement("div");
    check.className = "checkbox";
    row.appendChild(check);
    check.addEventListener("click", async (e) => {
      e.stopPropagation();
      check.classList.add("checked");
      card.classList.add("done");
      try {
        await onCheck();
      } catch (err) {
        check.classList.remove("checked");
        card.classList.remove("done");
        alert(err.message);
      }
    });
  }

  card.appendChild(row);

  if (expandHtml) {
    const expand = document.createElement("div");
    expand.className = "feed-expand";
    expand.innerHTML = expandHtml;
    card.appendChild(expand);
    card.addEventListener("click", (e) => {
      if (e.target.closest(".checkbox")) return;
      card.classList.toggle("open");
    });
  }

  return card;
}

async function loadDashboard() {
  renderDigestHeader();
  const feed = document.getElementById("digest-feed");
  feed.innerHTML = "";

  const [bills, subscriptions, maintenance, decisions] = await Promise.all([
    api("/api/bills").catch(() => []),
    api("/api/subscriptions").catch(() => []),
    api("/api/maintenance").catch(() => []),
    api("/api/decisions").catch(() => []),
  ]);

  const today = todayStr();

  const dueBills = bills.filter((b) => !b.paid && b.due_date <= today);
  const dueSubs = subscriptions.filter((s) => s.active && s.renewal_date <= today);
  const dueMaintenance = maintenance.filter((m) => m.next_due && m.next_due <= today);
  const openDecisions = decisions.filter((d) => d.status === "open");

  const dueCount = dueBills.length + dueSubs.length + dueMaintenance.length;
  const needCount = dueCount + openDecisions.length;
  document.getElementById("digest-sub").textContent =
    needCount === 0
      ? "Nothing needs you today — enjoy the calm."
      : `${needCount} thing${needCount === 1 ? "" : "s"} need${needCount === 1 ? "s" : ""} you today.`;

  if (dueCount > 0) {
    const label = document.createElement("div");
    label.className = "section-label";
    label.textContent = "Due today";
    feed.appendChild(label);

    for (const bill of dueBills) {
      const overdue = bill.due_date < today;
      feed.appendChild(buildFeedCard({
        icon: "💡", iconClass: "bill",
        title: bill.name,
        meta: `${fmtMoney(bill.amount)} · ${overdue ? "overdue" : "due today"}`,
        urgent: true,
        checkbox: true,
        onCheck: async () => {
          await api(`/api/bills/${bill.id}/mark-paid`, "POST");
          showToast("Marked as paid");
        },
      }));
    }

    for (const item of dueMaintenance) {
      const overdue = item.next_due < today;
      feed.appendChild(buildFeedCard({
        icon: "🔧", iconClass: "maintenance",
        title: item.task,
        meta: `${item.property_or_appliance} · ${overdue ? "overdue" : "due today"}`,
        urgent: overdue,
        checkbox: true,
        onCheck: async () => {
          await api(`/api/maintenance/${item.id}/mark-done`, "POST");
          showToast("Marked done");
        },
      }));
    }

    for (const sub of dueSubs) {
      feed.appendChild(buildFeedCard({
        icon: "🔁", iconClass: "subscription",
        title: sub.name,
        meta: `${fmtMoney(sub.cost)}/${sub.billing_cycle} · renews today`,
        checkbox: true,
        onCheck: async () => {
          await api(`/api/subscriptions/${sub.id}/renew`, "POST");
          showToast("Renewed");
        },
      }));
    }
  }

  const status = await api("/api/calendar/status").catch(() => null);
  if (status && status.configured && status.connected) {
    const events = await api("/api/calendar/events").catch(() => []);
    const todaysEvents = events.filter((e) => {
      const d = new Date(e.start_time);
      const pad = (n) => String(n).padStart(2, "0");
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` === today;
    });
    if (todaysEvents.length > 0) {
      const label = document.createElement("div");
      label.className = "section-label";
      label.textContent = "Today's calendar";
      feed.appendChild(label);

      for (const event of todaysEvents) {
        const start = new Date(event.start_time);
        const end = new Date(event.end_time);
        const time = event.all_day
          ? "All day"
          : `${start.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}` +
            ` – ${end.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
        const details = [event.description, event.location].filter(Boolean).map(escapeHtml).join(" · ");
        feed.appendChild(buildFeedCard({
          icon: "📅", iconClass: "calendar",
          title: event.title,
          meta: time + (event.location ? ` · ${event.location}` : ""),
          expandHtml: details ? `<p>${details}</p>` : `<p>No further details.</p>`,
        }));
      }
    }
  }

  if (openDecisions.length > 0) {
    const label = document.createElement("div");
    label.className = "section-label";
    label.textContent = "Family decisions";
    feed.appendChild(label);

    for (const decision of openDecisions) {
      feed.appendChild(buildFeedCard({
        icon: "🗳️", iconClass: "decision",
        title: decision.item,
        meta: "Open — awaiting a decision",
        expandHtml: `<p>${decision.notes ? escapeHtml(decision.notes) : "No notes yet. Head to Browse → Decisions to resolve it."}</p>`,
      }));
    }
  }

  const stubLabel = document.createElement("div");
  stubLabel.className = "section-label";
  stubLabel.textContent = "Coming soon";
  feed.appendChild(stubLabel);

  const mealCard = buildFeedCard({
    icon: "🍲", iconClass: "stub",
    title: "Meal plan",
    meta: "Not connected yet",
  });
  mealCard.classList.add("stub-card");
  mealCard.querySelector(".card-title").insertAdjacentHTML(
    "beforebegin", '<span class="stub-pill">stub</span>'
  );
  feed.appendChild(mealCard);

  const securityCard = buildFeedCard({
    icon: "🔒", iconClass: "stub",
    title: "Home security",
    meta: "Not connected yet",
  });
  securityCard.classList.add("stub-card");
  securityCard.querySelector(".card-title").insertAdjacentHTML(
    "beforebegin", '<span class="stub-pill">stub</span>'
  );
  feed.appendChild(securityCard);

  if (dueCount === 0 && openDecisions.length === 0 && feed.querySelectorAll(".feed-card").length === 2) {
    const empty = document.createElement("p");
    empty.className = "feed-empty";
    empty.textContent = "Nothing due, nothing waiting on you.";
    feed.insertBefore(empty, stubLabel);
  }
}

const composerInput = document.getElementById("composer-input");
const composerSend = document.getElementById("composer-send");

function sendComposer() {
  const value = composerInput.value.trim();
  if (!value) return;
  showToast("Quick-add isn't wired up yet — coming in a later phase.");
  composerInput.value = "";
}

composerSend.addEventListener("click", sendComposer);
composerInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendComposer();
});
