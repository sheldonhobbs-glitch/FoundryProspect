// Ember service worker.
// Phase 0: registered so the app is installable as a PWA. No offline caching
// strategy or push handling yet — Web Push (VAPID) lands in Phase 6.

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});
