// Shared "Install App" button wiring for any page that has a
// <button id="install-app-btn"> in its markup. Handles the three real
// states a mobile browser can be in: install prompt available (Android
// Chrome/Edge), already installed, or no native prompt at all (iOS
// Safari — those users need the manual Add to Home Screen / Share sheet
// route, which this shows instructions for instead of a broken button).

let deferredInstallPrompt = null;

window.addEventListener("beforeinstallprompt", (e) => {
	e.preventDefault();
	deferredInstallPrompt = e;
	const btn = document.getElementById("install-app-btn");
	if (btn) btn.style.display = "block";
});

window.addEventListener("appinstalled", () => {
	const btn = document.getElementById("install-app-btn");
	if (btn) btn.style.display = "none";
});

function elementalWireInstallButton() {
	const btn = document.getElementById("install-app-btn");
	if (!btn) return;

	const isStandalone = window.matchMedia("(display-mode: standalone)").matches
		|| window.navigator.standalone === true;
	if (isStandalone) {
		btn.style.display = "none";
		return;
	}

	const isIOS = /iphone|ipad|ipod/i.test(window.navigator.userAgent);
	if (isIOS) {
		btn.innerText = "Install: tap Share, then \u201cAdd to Home Screen\u201d";
		btn.style.display = "block";
		btn.onclick = () => {
			alert("On iPhone/iPad: tap the Share icon in Safari, then \u201cAdd to Home Screen.\u201d");
		};
		return;
	}

	btn.onclick = async () => {
		if (!deferredInstallPrompt) return;
		deferredInstallPrompt.prompt();
		await deferredInstallPrompt.userChoice;
		deferredInstallPrompt = null;
	};
}

document.addEventListener("DOMContentLoaded", elementalWireInstallButton);
