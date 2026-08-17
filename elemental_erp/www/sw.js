// Minimal service worker — just enough to satisfy PWA installability
// (Chrome/Android requires an active service worker with a fetch handler
// before it will offer "Add to Home Screen"). This does a light
// network-first cache of visited pages so a flaky factory-floor or gate
// connection doesn't show a blank white screen; it's not full offline
// support for the scan actions themselves, which need the server anyway.

const CACHE_NAME = "elemental-erp-shell-v1";

self.addEventListener("install", (event) => {
	self.skipWaiting();
});

self.addEventListener("activate", (event) => {
	event.waitUntil(
		caches.keys().then((names) =>
			Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
		)
	);
	self.clients.claim();
});

self.addEventListener("fetch", (event) => {
	if (event.request.method !== "GET") return;
	event.respondWith(
		fetch(event.request)
			.then((response) => {
				const copy = response.clone();
				caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
				return response;
			})
			.catch(() => caches.match(event.request))
	);
});
