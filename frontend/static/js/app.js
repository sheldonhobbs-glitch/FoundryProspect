const loginScreen = document.getElementById("login-screen");
const chatScreen = document.getElementById("chat-screen");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
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

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.hidden = true;
  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;

  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (res.ok) {
    loginForm.reset();
    showChat();
  } else {
    loginError.textContent = "Invalid username or password.";
    loginError.hidden = false;
  }
});

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
