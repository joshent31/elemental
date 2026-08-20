// Client script for Packaging Entry form.
// Adds: QC status check, link to Job/QR, and a "Mark Packaging Completed"
// button once all entries for the Job are submitted.

frappe.ui.form.on("Packaging Entry", {
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

		// --- QC status check ---
		if (frm.doc.qr_code_master) {
			frappe.db.get_value("QR Code Master", frm.doc.qr_code_master, "finished_good", (r) => {
				if (r && r.finished_good) {
					frappe.db.get_value(
						"QC Inspection",
						{ job: frm.doc.job, finished_good: r.finished_good },
						["status", "name"],
						(qc) => {
							if (qc && qc.status) {
								const color = qc.status === "Passed" ? "green" : qc.status === "Failed" ? "red" : "orange";
								frm.set_intro(
									`QC Inspection: ${qc.status} — ${qc.name}`,
									color
								);
							}
						}
					);
				}
			});
		}

		// --- Job status info ---
		if (frm.doc.job) {
			frappe.db.get_value("Job", frm.doc.job, ["status", "packaging_completed", "customer"], (r) => {
				if (r) {
					const terminal = ["Closed", "Cancelled"];
					if (terminal.includes(r.status)) {
						frm.set_intro(
							`This Job is ${r.status}. Packaging entries on terminal Jobs may be blocked.`,
							"red"
						);
					} else if (!r.packaging_completed) {
						// Offer the "Mark Packaging Completed" button
						frm.add_custom_button(
							"Mark Packaging Completed → Consume Material",
							() => {
								frappe.confirm(
									"This rolls up EVERY department's issued material for this Job into one " +
										"Job Material Consumption draft, for costing to review. Continue?",
									() => {
										frappe.call({
											method: "elemental_erp.api.mark_job_packaging_completed",
											args: { job: frm.doc.job },
											callback: (resp) => {
												if (resp.message) {
													frappe.show_alert(
														`Job Material Consumption ${resp.message.job_material_consumption} created (Draft).`
													);
													frm.reload_doc();
												}
											},
										});
									}
								);
							},
							"Actions"
						).addClass("btn-warning");
					}
				}
			});
		}

		// --- Create Packing Labels shortcut ---
		if (frm.doc.job && frm.doc.docstatus === 1) {
			frm.add_custom_button(
				"Create Packing Box Labels",
				() => {
					frappe.prompt(
						{
							fieldname: "total_boxes",
							label: "How many boxes/labels?",
							fieldtype: "Int",
							reqd: 1,
						},
						(values) => {
							frappe.call({
								method: "elemental_erp.api.create_packing_labels",
								args: { job: frm.doc.job, total_boxes: values.total_boxes },
								callback: (r) => {
									if (r.message) {
										frappe.show_alert(`${r.message.created} box labels created.`);
										frappe.set_route("List", "Packing Box", { job: frm.doc.job });
									}
								},
							});
						},
						"Create Packing Labels"
					);
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
						frm.set_value("packaging_cost", r.message);
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
					frm.set_value("packaging_cost", r.message);
				}
			},
		});
	}
}
