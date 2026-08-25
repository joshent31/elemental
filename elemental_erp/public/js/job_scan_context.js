(function () {
	"use strict";

	function extractJobCode(decodedText) {
		try {
			const url = new URL(decodedText, window.location.origin);
			return url.searchParams.get("job") || url.pathname.split("/").filter(Boolean).pop();
		} catch (error) {
			return (decodedText || "").trim();
		}
	}

	window.ElementalJobContext = class ElementalJobContext {
		constructor(options = {}) {
			this.currentJob = null;
			this.onActivated = options.onActivated || function () {};
			this.input = document.getElementById("job-context-code");
			this.info = document.getElementById("job-context-info");
			this.scanButton = document.getElementById("scan-job-context");
			this.enterButton = document.getElementById("enter-job-context");
			this.scanner = null;

			this.enterButton.onclick = () => this.activate(this.input.value);
			this.input.addEventListener("keydown", (event) => {
				if (event.key === "Enter") this.activate(this.input.value);
			});
			this.scanButton.onclick = () => this.startScanner();

			if (options.prefill) this.activate(options.prefill);
		}

		activate(jobCode) {
			const code = extractJobCode(jobCode);
			if (!code) {
				frappe.msgprint("Scan the Job QR or enter the Job code first.");
				return;
			}
			frappe.call({
				method: "elemental_erp.api.lookup_job",
				args: { job_code: code },
				callback: (response) => {
					if (!response.message) return;
					this.currentJob = response.message;
					this.input.value = this.currentJob.name;
					this.info.textContent =
						`Active Job: ${this.currentJob.name} — ${this.currentJob.job_name}` +
						(this.currentJob.job_location ? ` | ${this.currentJob.job_location}` : "");
					this.info.className = "alert alert-success";
					this.info.style.display = "block";
					this.onActivated(this.currentJob);
				},
			});
		}

		startScanner() {
			if (!this.scanner) this.scanner = new Html5Qrcode("scanner-job-context");
			ElementalQrCamera.addSelectorButton(document.getElementById("scanner-job-context"));
			ElementalQrCamera.start(
				this.scanner,
				{ fps: 10, qrbox: 220 },
				(decodedText) => {
					this.scanner.stop();
					this.activate(decodedText);
				}
			).catch(() => {});
		}

		get name() {
			return this.currentJob ? this.currentJob.name : null;
		}
	};
})();
