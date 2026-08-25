frappe.pages["label-print-center"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Label Print Center",
		single_column: true,
	});
	wrapper.label_print_center = new LabelPrintCenter(page);
};

frappe.pages["label-print-center"].on_page_show = function (wrapper) {
	if (wrapper.label_print_center) wrapper.label_print_center.apply_route_options();
};

class LabelPrintCenter {
	constructor(page) {
		this.page = page;
		this.make_layout();
		this.bind_actions();
		this.apply_route_options();
	}

	escape(value) {
		return frappe.utils.escape_html(String(value ?? ""));
	}

	make_layout() {
		this.$root = $(`
			<div class="label-print-center" style="max-width:1000px; padding:8px 0 30px;">
				<div class="card" style="padding:18px; margin-bottom:16px;">
					<div style="display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap;">
						<div style="min-width:280px; flex:1;">
							<label style="font-size:12px; color:#666; display:block;">Job</label>
							<div id="label-print-job-field"></div>
						</div>
						<button class="btn btn-primary" id="label-print-load">Load Job Labels</button>
					</div>
					<div id="label-print-summary" style="margin-top:14px; color:#666;">Select a Job to begin.</div>
				</div>

				<div class="card" style="padding:18px; margin-bottom:16px;">
					<h4 style="margin-top:0;">Packing Box Labels</h4>
					<p class="text-muted">Generate labels once, then print all labels or an exact inclusive range such as 1–10 or 11–20.</p>
					<div style="display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap; margin-bottom:14px;">
						<div style="width:180px;"><label>Total labels to generate</label><div id="label-print-total-field"></div></div>
						<button class="btn btn-default" id="label-print-generate">Generate &amp; Print All</button>
					</div>
					<h5>Add More Packing Labels</h5>
					<div style="display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap; margin-bottom:18px;">
						<div style="width:150px;"><label>New From Box No.</label><div id="label-create-from-field"></div></div>
						<div style="width:150px;"><label>New To Box No.</label><div id="label-create-to-field"></div></div>
						<button class="btn btn-default" id="label-create-range">Create &amp; Print New Range</button>
					</div>
					<h5>Print Existing Packing Labels</h5>
					<div style="display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap;">
						<div style="width:150px;"><label>From Box No.</label><div id="label-print-from-field"></div></div>
						<div style="width:150px;"><label>To Box No.</label><div id="label-print-to-field"></div></div>
						<button class="btn btn-primary" id="label-print-range">Print Selected Range</button>
						<button class="btn btn-default" id="label-print-all-boxes">Print All Packing Labels</button>
					</div>
				</div>

				<div class="card" style="padding:18px;">
					<h4 style="margin-top:0;">Job, Finished Good and Subpart Labels</h4>
					<div style="display:flex; gap:8px; flex-wrap:wrap;">
						<button class="btn btn-default" id="label-print-job-qr">Job QR Label</button>
						<button class="btn btn-default" id="label-print-traveller">Production Traveller</button>
						<button class="btn btn-primary" id="label-print-combined">Job + All FG + All Subparts</button>
						<button class="btn btn-default" id="label-print-fg">All FG / QC Labels</button>
						<button class="btn btn-default" id="label-print-subparts">All Subpart Labels</button>
					</div>
				</div>
			</div>
		`).appendTo(this.page.body);

		this.job_control = this.make_control("#label-print-job-field", {
			fieldtype: "Link",
			options: "Job",
			fieldname: "job",
			placeholder: "Select a Job",
		});
		this.total_control = this.make_control("#label-print-total-field", {
			fieldtype: "Int",
			fieldname: "total_labels",
			placeholder: "e.g. 20",
		});
		this.from_control = this.make_control("#label-print-from-field", {
			fieldtype: "Int",
			fieldname: "box_from",
			default: 1,
		});
		this.to_control = this.make_control("#label-print-to-field", {
			fieldtype: "Int",
			fieldname: "box_to",
		});
		this.create_from_control = this.make_control("#label-create-from-field", {
			fieldtype: "Int",
			fieldname: "create_box_from",
			default: 1,
		});
		this.create_to_control = this.make_control("#label-create-to-field", {
			fieldtype: "Int",
			fieldname: "create_box_to",
			default: 10,
		});

		const roles = frappe.user_roles || [];
		this.can_manage_boxes = [
			"System Manager",
			"Elemental Packaging User",
			"Elemental Packaging HOD",
		].some((role) => roles.includes(role));
		this.can_print_boxes = this.can_manage_boxes || roles.includes("Elemental Dispatch HOD");
		this.can_print_fg = [
			"System Manager",
			"Elemental QC User",
			"Elemental QC HOD",
			"Elemental Packaging HOD",
		].some((role) => roles.includes(role));
		this.can_print_subparts = [
			"System Manager",
			"Elemental Data Entry User",
			"Elemental Data Entry HOD",
			"Elemental Production User",
			"Elemental Production HOD",
			"Elemental Packaging User",
			"Elemental Packaging HOD",
		].some((role) => roles.includes(role));
		$("#label-print-generate", this.$root).toggle(this.can_manage_boxes);
		$("#label-create-range", this.$root).toggle(this.can_manage_boxes);
		$("#label-print-range, #label-print-all-boxes", this.$root).toggle(this.can_print_boxes);
		$("#label-print-fg", this.$root).toggle(this.can_print_fg);
		$("#label-print-subparts", this.$root).toggle(this.can_print_subparts);
	}

	make_control(selector, df) {
		const control = frappe.ui.form.make_control({
			df,
			parent: $(selector, this.$root),
			only_input: true,
			render_input: true,
		});
		control.refresh();
		return control;
	}

	bind_actions() {
		$("#label-print-load", this.$root).on("click", () => this.load_job());
		$("#label-print-generate", this.$root).on("click", () => this.generate_packing_labels());
		$("#label-create-range", this.$root).on("click", () => this.generate_packing_label_range());
		$("#label-print-range", this.$root).on("click", () => this.print_packing_labels(true));
		$("#label-print-all-boxes", this.$root).on("click", () => this.print_packing_labels(false));
		$("#label-print-job-qr", this.$root).on("click", () => this.print_job_format("Job QR Label"));
		$("#label-print-combined", this.$root).on("click", () =>
			this.print_job_format("Job All Production QR Labels")
		);
		$("#label-print-fg", this.$root).on("click", () => this.open_api("download_job_fg_labels"));
		$("#label-print-subparts", this.$root).on("click", () =>
			this.open_api("download_job_subpart_labels")
		);
		$("#label-print-traveller", this.$root).on("click", () => this.print_traveller());
	}

	apply_route_options() {
		const options = frappe.route_options || {};
		frappe.route_options = null;
		if (!options.job || !this.job_control) return;
		this.job_control.set_value(options.job);
		setTimeout(() => this.load_job(), 0);
	}

	get_job() {
		const job = this.job_control.get_value();
		if (!job) frappe.msgprint("Select a Job first.");
		return job;
	}

	load_job() {
		const job = this.get_job();
		if (!job) return;
		frappe.call({
			method: "elemental_erp.api.get_label_print_center_data",
			args: { job },
			freeze: true,
			callback: (response) => {
				const data = response.message;
				if (!data) return;
				const boxes = data.packing_boxes;
				const detail = data.job;
				$("#label-print-summary", this.$root).html(
					`<b>${this.escape(detail.name)}</b> — ${this.escape(detail.job_name)} | ` +
					`${this.escape(detail.customer)} | Status: ${this.escape(detail.status)}<br>` +
					`Available packing labels: <b>${boxes.count}</b>` +
					(boxes.count ? ` (Box ${boxes.first} to ${boxes.last})` : "")
				);
				if (boxes.configured_total) this.total_control.set_value(boxes.configured_total);
				if (boxes.count) {
					this.from_control.set_value(boxes.first);
					this.to_control.set_value(boxes.last);
				}
				this.create_from_control.set_value(boxes.next_number);
				this.create_to_control.set_value(Math.min(boxes.next_number + 9, 1000));
				$("#label-print-generate", this.$root)
					.prop("disabled", boxes.existing_count > 0)
					.text(
						boxes.existing_count > 0
							? "Packing Labels Already Generated"
							: "Generate & Print All"
					);
			},
		});
	}

	generate_packing_labels() {
		const job = this.get_job();
		const total_boxes = this.total_control.get_value();
		if (!job || !total_boxes || total_boxes <= 0) {
			if (job) frappe.msgprint("Enter how many packing labels to generate.");
			return;
		}
		const print_window = window.open("about:blank", "_blank");
		frappe.call({
			method: "elemental_erp.api.create_packing_labels",
			args: { job, total_boxes },
			freeze: true,
			freeze_message: "Generating packing box QR labels...",
			callback: (response) => {
				if (!response.message) {
					if (print_window) print_window.close();
					return;
				}
				frappe.show_alert(`${response.message.created} packing labels generated.`);
				if (print_window) {
					print_window.location =
						`/api/method/elemental_erp.api.download_packing_labels?job=${encodeURIComponent(job)}`;
				}
				this.load_job();
			},
			error: () => {
				if (print_window) print_window.close();
			},
		});
	}

	generate_packing_label_range() {
		const job = this.get_job();
		const box_from = this.create_from_control.get_value();
		const box_to = this.create_to_control.get_value();
		if (!job || !box_from || !box_to || box_from > box_to) {
			if (job) frappe.msgprint("Enter a valid new packing-label range.");
			return;
		}
		const print_window = window.open("about:blank", "_blank");
		frappe.call({
			method: "elemental_erp.api.create_packing_label_range",
			args: { job, box_from, box_to },
			freeze: true,
			freeze_message: `Generating Packing Box labels ${box_from} to ${box_to}...`,
			callback: (response) => {
				if (!response.message) {
					if (print_window) print_window.close();
					return;
				}
				frappe.show_alert(`${response.message.created} new packing labels generated.`);
				if (print_window) {
					const params = new URLSearchParams({ job, box_from, box_to });
					print_window.location =
						`/api/method/elemental_erp.api.download_packing_labels?${params.toString()}`;
				}
				this.load_job();
			},
			error: () => {
				if (print_window) print_window.close();
			},
		});
	}

	print_packing_labels(selected_range) {
		const job = this.get_job();
		if (!job) return;
		const args = { job };
		if (selected_range) {
			args.box_from = this.from_control.get_value();
			args.box_to = this.to_control.get_value();
			if (!args.box_from || !args.box_to || args.box_from > args.box_to) {
				frappe.msgprint("Enter a valid From Box No. and To Box No.");
				return;
			}
		}
		this.open_api("download_packing_labels", args);
	}

	print_job_format(format) {
		const job = this.get_job();
		if (!job) return;
		window.open(
			`/printview?doctype=Job&name=${encodeURIComponent(job)}` +
				`&format=${encodeURIComponent(format)}&no_letterhead=1`,
			"_blank"
		);
	}

	print_traveller() {
		const job = this.get_job();
		if (!job) return;
		const print_window = window.open("about:blank", "_blank");
		frappe.call({
			method: "elemental_erp.api.prepare_job_production_traveller",
			args: { job },
			freeze: true,
			callback: (response) => {
				if (response.message && print_window) print_window.location = response.message.print_url;
			},
			error: () => {
				if (print_window) print_window.close();
			},
		});
	}

	open_api(method, extra_args = {}) {
		const job = extra_args.job || this.get_job();
		if (!job) return;
		const params = new URLSearchParams({ job, ...extra_args });
		window.open(`/api/method/elemental_erp.api.${method}?${params.toString()}`, "_blank");
	}
}
