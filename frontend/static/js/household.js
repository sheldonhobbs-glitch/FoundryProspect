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
  },
  maintenance: {
    label: "Maintenance",
    endpoint: "/api/maintenance",
    fields: [
      { name: "task", label: "Task", type: "text", required: true },
      { name: "property_or_appliance", label: "Property / appliance", type: "text", required: true },
      { name: "last_done", label: "Last done (optional)", type: "date" },
      { name: "next_due", label: "Next due (optional)", type: "date" },
      { name: "notes", label: "Notes", type: "textarea" },
    ],
    renderCard(item) {
      return `<strong>${escapeHtml(item.task)}</strong> (${escapeHtml(item.property_or_appliance)})<br>
        last done ${item.last_done ?? "never"} · next due ${item.next_due ?? "—"}`;
    },
    actions(item, refresh) {
      return [
        { label: "Mark done", onClick: () => api(`/api/maintenance/${item.id}/mark-done`, "POST").then(refresh) },
      ];
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
        o.textContent = opt.replace("_", " ");
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
  const bubble = document.createElement("div");
  bubble.className = "bubble system resource-bubble";

  const title = document.createElement("div");
  title.className = "resource-title";
  title.textContent = config.label;
  bubble.appendChild(title);

  const listEl = document.createElement("div");
  bubble.appendChild(listEl);

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "add-btn";
  addBtn.textContent = `+ Add ${config.label.toLowerCase().replace(/s$/, "")}`;
  bubble.appendChild(addBtn);

  chatLog.appendChild(bubble);
  chatLog.scrollTop = chatLog.scrollHeight;

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
    const existingForm = bubble.querySelector(".resource-form:not(.resource-card .resource-form)");
    if (existingForm) {
      existingForm.remove();
      return;
    }
    const form = buildForm(resourceKey, null, () => {
      form.remove();
      refresh();
    });
    bubble.insertBefore(form, addBtn);
  });

  await refresh();
}

async function loadNotifications() {
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
    chatLog.appendChild(bubble);
  }
}

document.querySelectorAll("#quick-actions button").forEach((btn) => {
  btn.addEventListener("click", () => openResource(btn.dataset.resource));
});
