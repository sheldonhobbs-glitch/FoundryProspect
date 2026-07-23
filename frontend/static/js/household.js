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
  warranties: {
    label: "Warranties",
    endpoint: "/api/warranties",
    fields: [
      { name: "item", label: "Item", type: "text", required: true },
      { name: "purchase_date", label: "Purchase date", type: "date", required: true },
      { name: "expiry_date", label: "Expiry date", type: "date", required: true },
      { name: "document_reference", label: "Document reference (optional)", type: "text" },
      { name: "notes", label: "Notes", type: "textarea" },
    ],
    renderCard(item) {
      const doc = item.document_reference ? ` · doc: ${escapeHtml(item.document_reference)}` : "";
      return `<strong>${escapeHtml(item.item)}</strong><br>
        purchased ${item.purchase_date} · expires ${item.expiry_date}${doc}`;
    },
    actions() {
      return [];
    },
    count(items) {
      return items.length === 0 ? "" : `${items.length} item${items.length === 1 ? "" : "s"}`;
    },
  },
  decisions: {
    label: "Decisions",
    endpoint: "/api/decisions",
    fields: [
      { name: "item", label: "Thing to decide", type: "text", required: true },
      { name: "notes", label: "Notes", type: "textarea" },
    ],
    renderCard(item) {
      if (item.status === "decided") {
        return `<strong>${escapeHtml(item.item)}</strong> · ✅ decided ${item.decided_at}<br>
          ${escapeHtml(item.decision)}`;
      }
      const notes = item.notes ? `<br><span class="muted">${escapeHtml(item.notes)}</span>` : "";
      return `<strong>${escapeHtml(item.item)}</strong> · open${notes}`;
    },
    actions(item, refresh) {
      if (item.status === "decided") {
        return [
          { label: "Reopen", onClick: () => api(`/api/decisions/${item.id}/reopen`, "POST").then(refresh) },
        ];
      }
      return [
        {
          label: "Resolve",
          onClick: async () => {
            const decision = prompt(`What was decided about "${item.item}"?`);
            if (!decision || !decision.trim()) return;
            await api(`/api/decisions/${item.id}/resolve`, "POST", { decision });
            refresh();
          },
        },
      ];
    },
    count(items) {
      const open = items.filter((i) => i.status === "open").length;
      return items.length === 0 ? "" : open === 0 ? "all decided" : `${open} open`;
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

document.querySelectorAll(".section-tile").forEach((btn) => {
  btn.addEventListener("click", () => {
    const key = btn.dataset.resource;
    if (key === "calendar") {
      openCalendar();
    } else {
      openResource(key);
    }
  });
});

async function refreshHomeCounts() {
  for (const [key, config] of Object.entries(RESOURCES)) {
    const el = document.querySelector(`[data-count-for="${key}"]`);
    if (!el) continue;
    try {
      const items = await api(config.endpoint);
      el.textContent = config.count(items);
    } catch {
      el.textContent = "";
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

function localInputToIso(value) {
  return new Date(value).toISOString();
}

function isoToLocalInput(iso) {
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function renderEventCard(event) {
  const start = new Date(event.start_time);
  const end = new Date(event.end_time);
  const fmt = event.all_day
    ? "All day"
    : `${start.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}` +
      ` – ${end.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
  const loc = event.location ? ` · ${escapeHtml(event.location)}` : "";
  return `<strong>${escapeHtml(event.title)}</strong><br>${fmt}${loc}`;
}

function groupEventsByDay(events) {
  const groups = [];
  let currentKey = null;
  let currentGroup = null;
  for (const event of events) {
    const d = new Date(event.start_time);
    const key = d.toDateString();
    if (key !== currentKey) {
      currentKey = key;
      currentGroup = { label: d.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" }), events: [] };
      groups.push(currentGroup);
    }
    currentGroup.events.push(event);
  }
  return groups;
}

function buildEventForm(existing, onDone) {
  const form = document.createElement("form");
  form.className = "resource-form";

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

  const listEl = document.createElement("div");
  detailBody.appendChild(listEl);

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "add-btn";
  addBtn.textContent = "+ Add event";
  detailBody.appendChild(addBtn);

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
      card.appendChild(buildEventForm(event, refresh));
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

  async function refresh() {
    const events = await api("/api/calendar/events");
    listEl.innerHTML = "";
    if (events.length === 0) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "No events in the next ~3 months.";
      listEl.appendChild(empty);
      return;
    }
    for (const group of groupEventsByDay(events)) {
      const header = document.createElement("div");
      header.className = "day-header";
      header.textContent = group.label;
      listEl.appendChild(header);

      for (const event of group.events) {
        const card = document.createElement("div");
        card.className = "resource-card";
        card.innerHTML = renderEventCard(event);
        renderEventActions(event, card, refresh);
        listEl.appendChild(card);
      }
    }
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

  addBtn.addEventListener("click", () => {
    const existingForm = detailBody.querySelector(".resource-form");
    if (existingForm) {
      existingForm.remove();
      return;
    }
    const form = buildEventForm(null, () => {
      form.remove();
      refresh();
    });
    detailBody.insertBefore(form, addBtn);
  });

  await refresh();
}

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
