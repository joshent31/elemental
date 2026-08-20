// Client script for Dispatch Entry form.
// Adds: view Job/boxes, dispatch status actions, and auto-compute cost.

frappe.ui.form.on("Dispatch Entry", {
	refresh(frm) {
		if (frm.is_new()) return;

		// --- View shortcuts ---
		if (frm.doc.job) {
			frm.add_custom_button(
				"View Job",
				() => frappe.set_route("Form", "Job", frm.doc.job),
				"View"
			);
			frm.add_custom_button(
				"View Packing Boxes",
				() => frappe.set_route("List", "Packing Box", { job: frm.doc.job }),
				"View"
			);
		}

		// --- Box loading progress ---
		if (frm.doc.job) {
			frappe.call({
				method: "elemental_erp.api.get_job_box_progress",
				args: { job: frm.doc.job },
				callback: (r) => {
					if (r.message) {
						const p = r.message;
						const color = p.dispatched >= p.total ? "green" : "blue";
						frm.set_intro(
							`Boxes: ${p.packed} packed, ${p.dispatched} loaded/dispatched, ${p.total} total`,
							color
						);
					}
				},
			});
		}

		// --- Job status info ---
		if (frm.doc.job) {
			frappe.db.get_value("Job", frm.doc.job, ["status", "packaging_completed", "customer"], (r) => {
				if (r) {
					const terminal = ["Closed", "Cancelled"];
					if (terminal.includes(r.status)) {
						frm.set_intro(
							`This Job is ${r.status}. Dispatch entries on terminal Jobs may be blocked.`,
							"red"
						);
					} else if (!r.packaging_completed) {
						frm.set_intro(
							"Packaging has not been marked completed for this Job yet.",
							"orange"
						);
					}
				}
			});
		}

		// --- Dispatch actions ---
		if (frm.doc.docstatus === 1) {
			// Mark as Dispatched
			if (frm.doc.dispatch_status === "Scheduled") {
				frm.add_custom_button(
					"Mark as Dispatched",
					() => {
						frappe.confirm(
							"Mark this dispatch as dispatched? This will update the Job status.",
							() => {
								frm.set_value("dispatch_status", "Dispatched");
								frm.save();
							}
						);
					},
					"Actions"
				).addClass("btn-primary");
			}

			// Mark as Delivered
			if (frm.doc.dispatch_status === "Dispatched") {
				frm.add_custom_button(
					"Mark as Delivered",
					() => {
						frappe.confirm(
							"Mark this dispatch as delivered? This will close the Job.",
							() => {
								frm.set_value("dispatch_status", "Delivered");
								frm.save();
							}
						);
					},
					"Actions"
				).addClass("btn-success");
			}

			// Create Sales Invoice
			frm.add_custom_button(
				"Create Sales Invoice",
				() => {
					frappe.call({
						method: "elemental_erp.api.create_sales_invoice_for_job",
						args: { job: frm.doc.job },
						callback: (r) => {
							if (r.message) {
								if (r.message.skipped_fgs && r.message.skipped_fgs.length) {
									frappe.msgprint(`Skipped (no ERPNext Item mapped): ${r.message.skipped_fgs.join(", ")}`);
								}
								frappe.set_route("Form", "Sales Invoice", r.message.sales_invoice);
							}
						},
					});
				},
				"Actions"
			);

			// Dispatch scan page shortcut
			frm.add_custom_button(
				"Open Dispatch Scan",
				() => {
					window.open(`/dispatch-scan`, "_blank");
				},
				"Actions"
			);
		}

		// --- Cost computation ---
		if (frm.doc.employee && frm.doc.hours_spent) {
			frappe.call({
				method: "elemental_erp.utils.costing.compute_cost",
				args: { employee: frm.doc.employee, hours: frm.doc.hours_spent },
				callback: (r) => {
					if (r.message !== undefined) {
						frm.set_value("dispatch_cost", r.message);
					}
				},
			});
		}
	},

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
			args: { employee: frm.doc.employee, hours: frm.doc.hours_spent },
			callback: (r) => {
				if (r.message !== undefined) {
					frm.set_value("dispatch_cost", r.message);
				}
			},
		});
	}
}
