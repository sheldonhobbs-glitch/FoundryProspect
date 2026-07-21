const loginScreen = document.getElementById("login-screen");
const chatScreen = document.getElementById("chat-screen");
const logoutBtn = document.getElementById("logout-btn");
const chatLog = document.getElementById("chat-log");

function addBubble(text, kind = "system") {
  const div = document.createElement("div");
  div.className = `bubble ${kind}`;
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function showChat() {
  loginScreen.hidden = true;
  chatScreen.hidden = false;
  chatLog.innerHTML = "";
  addBubble("Welcome back. Ember is online.");
  fetch("/api/health")
    .then((r) => r.json())
    .then((data) => {
      addBubble(
        data.database
          ? "Database connection: healthy."
          : "Database connection: unreachable — check DATABASE_URL.",
      );
    })
    .catch(() => addBubble("Could not reach the API."));
  if (window.loadNotifications) loadNotifications();
}

function showLogin() {
  chatScreen.hidden = true;
  loginScreen.hidden = false;
}

async function checkSession() {
  const res = await fetch("/api/auth/me");
  const data = await res.json();
  if (data.authenticated) {
    showChat();
  } else {
    showLogin();
  }
}

logoutBtn.addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST" });
  showLogin();
});

checkSession();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {
      // Non-fatal: app works without the service worker, just without offline/push support.
    });
  });
}
