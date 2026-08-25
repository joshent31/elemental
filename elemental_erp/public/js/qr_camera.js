(function () {
	"use strict";

	const STORAGE_KEY = "elemental_qr_camera_id";

	function cameraError(error) {
		const detail = error && (error.message || error.name || String(error));
		if (!window.isSecureContext && !["localhost", "127.0.0.1"].includes(window.location.hostname)) {
			return "Camera access is blocked on an insecure HTTP page. Open this ERP site using HTTPS, then allow camera permission.";
		}
		if (/NotAllowed|Permission/i.test(detail || "")) {
			return "Camera permission was denied. Allow Camera for this site in the browser address-bar settings and try again.";
		}
		if (/NotFound|DevicesNotFound/i.test(detail || "")) {
			return "No camera was found. Connect or enable the laptop/USB webcam and try again.";
		}
		return `Unable to start the camera${detail ? `: ${detail}` : "."}`;
	}

	async function chooseCamera(cameras) {
		const saved = localStorage.getItem(STORAGE_KEY);
		if (saved && cameras.some((camera) => camera.id === saved)) return saved;
		const rear = cameras.find((camera) => /back|rear|environment/i.test(camera.label || ""));
		const selected = rear || cameras[0];
		if (selected) localStorage.setItem(STORAGE_KEY, selected.id);
		return selected && selected.id;
	}

	async function start(scanner, scanConfig, onSuccess, onFailure) {
		try {
			if (!window.isSecureContext && !["localhost", "127.0.0.1"].includes(window.location.hostname)) {
				throw new Error("INSECURE_CAMERA_CONTEXT");
			}
			const cameras = await Html5Qrcode.getCameras();
			if (!cameras.length) throw new Error("No camera found");
			const cameraId = await chooseCamera(cameras);
			return await scanner.start(cameraId, scanConfig, onSuccess, onFailure || function () {});
		} catch (error) {
			frappe.msgprint({ title: "Camera unavailable", message: cameraError(error), indicator: "red" });
			throw error;
		}
	}

	async function selectCamera() {
		try {
			const cameras = await Html5Qrcode.getCameras();
			if (!cameras.length) throw new Error("No camera found");
			const options = cameras.map((camera, index) => ({ label: camera.label || `Camera ${index + 1}`, value: camera.id }));
			frappe.prompt(
				[{ fieldname: "camera", label: "Camera", fieldtype: "Select", options, default: localStorage.getItem(STORAGE_KEY) || options[0].value, reqd: 1 }],
				(values) => { localStorage.setItem(STORAGE_KEY, values.camera); frappe.show_alert({ message: "Camera preference saved.", indicator: "green" }); },
				"Select QR Camera"
			);
		} catch (error) {
			frappe.msgprint({ title: "Camera unavailable", message: cameraError(error), indicator: "red" });
		}
	}

	function addSelectorButton(container) {
		if (!container || document.getElementById("elemental-select-camera")) return;
		const button = document.createElement("button");
		button.id = "elemental-select-camera";
		button.type = "button";
		button.className = "btn btn-default btn-sm";
		button.style.margin = "0 0 8px";
		button.textContent = "Select Laptop / USB Camera";
		button.onclick = selectCamera;
		container.parentNode.insertBefore(button, container);
	}

	window.ElementalQrCamera = { start, selectCamera, addSelectorButton };
})();
