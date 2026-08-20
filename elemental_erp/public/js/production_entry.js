// Client script for Production Entry form.
// Adds: link to Job, view QR status, auto-fill from Job context,
// and a warning if the Job is in a terminal state.

frappe.ui.form.on("Production Entry", {
	refresh(frm) {
		if (frm.is_new()) return;

		// --- View shortcuts ---
		if (frm.doc.job) {
			frm.add_custom_button(
				"View Job",
				() => frappe.set_route("Form", "Job", frm.doc.job),
				"View"
			);
		}
		if (frm.doc.qr_code_master) {
			frm.add_custom_button(
				"View QR Status",
				() => frappe.set_route("Form", "QR Code Master", frm.doc.qr_code_master),
				"View"
			);
		}

		// --- Job status info ---
		if (frm.doc.job) {
			frappe.db.get_value("Job", frm.doc.job, ["status", "customer", "job_name"], (r) => {
				if (r) {
					const terminal = ["Closed", "Cancelled"];
					if (terminal.includes(r.status)) {
						frm.set_intro(
							`This Job is ${r.status}. Production entries on terminal Jobs may be blocked.`,
							"red"
						);
					} else {
						frm.set_intro(
							`Job: ${r.job_name || frm.doc.job} — Customer: ${r.customer || "—"} — Status: ${r.status}`,
							"blue"
						);
					}
				}
			});
		}

		// --- Mark dispatch status on submit ---
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(
				"Mark as Dispatched",
				() => {
					frappe.confirm(
						"Mark this Production Entry's Job as Dispatched? Only do this if all production is complete.",
						() => {
							frappe.call({
								method: "frappe.client.set_value",
								args: {
									doctype: "Job",
									name: frm.doc.job,
									fieldname: "status",
									value: "Dispatched",
								},
								callback: () => frm.reload_doc(),
							});
						}
					);
				},
				"Status"
			);
		}
	},

	// Auto-compute cost when hours or employee change
	hours_spent(frm) {
		_compute_cost(frm);
	},
	employee(frm) {
		_compute_cost(frm);
	},
});

function _compute_cost(frm) {
	if (frm.doc.employee && frm.doc.hours_spent) {
		frappe.call({
			method: "elemental_erp.utils.costing.compute_cost",
			args: {
				employee: frm.doc.employee,
				hours: frm.doc.hours_spent,
			},
			callback: (r) => {
				if (r.message !== undefined) {
					frm.set_value("production_cost", r.message);
				}
			},
		});
	}
}
