// Ember composer: sends what you type to the Ember Brain and shows the reply,
// what was done, and anything waiting for your confirmation. All the
// intelligence is server-side; this file only renders. Model text is always
// inserted with textContent, never as HTML.

(function () {
  const form = document.getElementById("composer-form");
  const input = document.getElementById("composer-input");
  const sendBtn = document.getElementById("composer-send");
  const panel = document.getElementById("ember-panel");
  const thread = document.getElementById("ember-thread");
  const closeBtn = document.getElementById("ember-panel-close");

  let busy = false;
  let restored = false;

  function openPanel() {
    panel.hidden = false;
  }

  function closePanel() {
    panel.hidden = true;
  }

  function scrollToEnd() {
    thread.scrollTop = thread.scrollHeight;
  }

  function addBubble(role, text) {
    const bubble = document.createElement("div");
    bubble.className = `ember-msg ${role}`;
    bubble.textContent = text;
    thread.appendChild(bubble);
    scrollToEnd();
    return bubble;
  }

  function addDone(summary) {
    const line = document.createElement("div");
    line.className = "ember-done";
    line.textContent = summary;
    thread.appendChild(line);
  }

  function addThinking() {
    const el = document.createElement("div");
    el.className = "ember-msg assistant ember-thinking";
    el.setAttribute("aria-label", "Ember is thinking");
    el.innerHTML = "<span></span><span></span><span></span>";
    thread.appendChild(el);
    scrollToEnd();
    return el;
  }

  function addConfirmCard(pending) {
    const card = document.createElement("div");
    card.className = "ember-confirm";

    const text = document.createElement("div");
    text.className = "ember-confirm-text";
    text.textContent = pending.summary;
    card.appendChild(text);

    const actions = document.createElement("div");
    actions.className = "ember-confirm-actions";
    const confirm = document.createElement("button");
    confirm.type = "button";
    confirm.className = "ember-confirm-yes";
    confirm.textContent = "Confirm";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "ember-confirm-no";
    cancel.textContent = "Cancel";
    actions.append(confirm, cancel);
    card.appendChild(actions);

    function resolve(message, ok) {
      actions.remove();
      const outcome = document.createElement("div");
      outcome.className = `ember-confirm-outcome ${ok ? "ok" : "no"}`;
      outcome.textContent = message;
      card.appendChild(outcome);
    }

    confirm.addEventListener("click", async () => {
      confirm.disabled = cancel.disabled = true;
      try {
        const res = await api(`/api/ember/actions/${pending.id}/confirm`, "POST");
        resolve(res.result, true);
        refreshScreens();
      } catch (err) {
        resolve(err.message, false);
      }
    });
    cancel.addEventListener("click", async () => {
      confirm.disabled = cancel.disabled = true;
      try {
        await api(`/api/ember/actions/${pending.id}/cancel`, "POST");
        resolve("Cancelled — nothing was changed.", false);
      } catch (err) {
        resolve(err.message, false);
      }
    });

    thread.appendChild(card);
    scrollToEnd();
  }

  // After Ember changes something, make the screen behind it match.
  function refreshScreens() {
    const home = document.getElementById("home-view");
    const browse = document.getElementById("browse-view");
    if (home && !home.hidden && typeof loadDashboard === "function") loadDashboard();
    if (browse && !browse.hidden && typeof refreshHomeCounts === "function") refreshHomeCounts();
  }

  async function send(text) {
    busy = true;
    sendBtn.disabled = true;
    openPanel();
    addBubble("user", text);
    const thinking = addThinking();
    try {
      const res = await api("/api/ember/message", "POST", { text });
      thinking.remove();
      addBubble("assistant", res.reply);
      res.actions.forEach((a) => addDone(a.summary));
      res.pending.forEach(addConfirmCard);
      scrollToEnd();
      if (res.actions.length) refreshScreens();
    } catch (err) {
      thinking.remove();
      addBubble("error", err.message || "Something went wrong. Try again.");
    } finally {
      busy = false;
      sendBtn.disabled = false;
      input.focus();
    }
  }

  // Bring back an in-progress conversation (e.g. after a reload).
  async function restore() {
    if (restored) return;
    restored = true;
    try {
      const convo = await api("/api/ember/conversation");
      if (!convo.messages.length) return;
      thread.innerHTML = "";
      convo.messages.forEach((m) => addBubble(m.role, m.text));
      convo.pending.forEach(addConfirmCard);
      openPanel();
    } catch {
      // Not fatal — the composer still works without history.
    }
  }

  function reset() {
    thread.innerHTML = "";
    restored = false;
    closePanel();
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || busy) return;
    input.value = "";
    restored = true;
    send(text);
  });
  input.addEventListener("focus", restore);
  closeBtn.addEventListener("click", closePanel);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) closePanel();
  });
  // Conversations belong to a person; switching or logging out starts clean.
  document.getElementById("identity-btn").addEventListener("click", reset);
  document.getElementById("logout-btn").addEventListener("click", reset);
})();
