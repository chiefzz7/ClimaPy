/* Service Worker do ClimaPy: cache seguro de shell + Web Push anônimo */
const SHELL_CACHE = "climapy-shell-v1";
const SHELL_ASSETS = [
  "/",
  "/index.html",
  "/manifest.webmanifest",
  "/icons/icon.svg",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key !== SHELL_CACHE).map((oldKey) => caches.delete(oldKey))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") {
    return;
  }
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    return;
  }
  /* Nunca cachear endpoints /api/ para não armazenar respostas sensíveis/tokens no CacheStorage */
  if (url.pathname.startsWith("/api/")) {
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          if (networkResponse.ok) {
            const copy = networkResponse.clone();
            caches.open(SHELL_CACHE).then((cache) => cache.put("/index.html", copy));
          }
          return networkResponse;
        })
        .catch(() => caches.match("/index.html"))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }
      return fetch(request).then((networkResponse) => {
        if (networkResponse.ok && networkResponse.type === "basic") {
          const copy = networkResponse.clone();
          caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy));
        }
        return networkResponse;
      });
    })
  );
});

self.addEventListener("push", (event) => {
  let payload = {
    title: "ClimaPy",
    body: "Confira a previsão do tempo atualizada.",
    tag: "climapy-weather",
    url: "/",
  };
  if (event.data) {
    try {
      const parsed = event.data.json();
      if (parsed && typeof parsed === "object") {
        payload = {
          title: typeof parsed.title === "string" ? parsed.title : payload.title,
          body: typeof parsed.body === "string" ? parsed.body : payload.body,
          tag: typeof parsed.tag === "string" ? parsed.tag : payload.tag,
          url: typeof parsed.url === "string" ? parsed.url : "/",
        };
      }
    } catch {
      const text = event.data.text();
      if (text) {
        payload.body = text;
      }
    }
  }

  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      tag: payload.tag,
      data: { url: payload.url },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl =
    event.notification.data && typeof event.notification.data.url === "string"
      ? event.notification.data.url
      : "/";

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ("focus" in client) {
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
      return undefined;
    })
  );
});
