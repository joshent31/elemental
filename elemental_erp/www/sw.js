// Minimal service worker for PWA installability. Authentication pages,
// user-specific HTML and API responses must never be cached: these devices can
// be shared and a previous operator's data must not be shown after sign-out.
// Only versioned/static Elemental assets are safe to cache.

const CACHE_NAME = "elemental-erp-static-v2";

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
	const requestUrl = new URL(event.request.url);
	const isStaticElementalAsset = requestUrl.origin === self.location.origin
		&& requestUrl.pathname.startsWith("/assets/elemental_erp/");
	if (!isStaticElementalAsset) return;
	event.respondWith(
		caches.match(event.request).then((cached) => cached || fetch(event.request)
			.then((response) => {
				if (response.ok) {
					const copy = response.clone();
					caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
				}
				return response;
			}))
	);
});
