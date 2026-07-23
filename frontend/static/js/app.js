const loginScreen = document.getElementById("login-screen");
const identityScreen = document.getElementById("identity-screen");
const mainScreen = document.getElementById("main-screen");
const logoutBtn = document.getElementById("logout-btn");
const statusBubble = document.getElementById("status-bubble");

function setStatus(text) {
  statusBubble.textContent = text;
  statusBubble.hidden = false;
}

function showMain() {
  loginScreen.hidden = true;
  identityScreen.hidden = true;
  mainScreen.hidden = false;
  statusBubble.hidden = true;

  fetch("/api/health")
    .then((r) => r.json())
    .then((data) => {
      if (!data.database) setStatus("Database connection: unreachable — check DATABASE_URL.");
    })
    .catch(() => setStatus("Could not reach the API."));

  if (window.applyIdentity) applyIdentity(window.currentIdentity);
  if (window.showHome) showHome();
}

function showIdentityPicker() {
  loginScreen.hidden = true;
  mainScreen.hidden = true;
  identityScreen.hidden = false;
}

function showLogin() {
  identityScreen.hidden = true;
  mainScreen.hidden = true;
  loginScreen.hidden = false;
}

async function checkSession() {
  const res = await fetch("/api/auth/me");
  const data = await res.json();
  if (!data.authenticated) {
    showLogin();
    return;
  }
  const identityRes = await fetch("/api/auth/identity");
  const identityData = await identityRes.json();
  window.currentIdentity = identityData.identity;
  if (!identityData.identity) {
    showIdentityPicker();
  } else {
    showMain();
  }
}

logoutBtn.addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST" });
  window.currentIdentity = null;
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
