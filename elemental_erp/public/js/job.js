// Client script for the Job form. Job is NOT submittable — it stays open
// so new Finished Goods can be added by the customer at any point, right
// up until it's explicitly Closed (or Cancelled). Action buttons are
// gated on "!frm.is_new()", not docstatus (Job has no submit lifecycle),
// and disappear once the Job reaches a terminal status.

window.elemental_print_all_packing_labels = function (job) {
	if (!job) {
		frappe.msgprint("Select a Job first.");
		return;
	}
	const url = `/api/method/elemental_erp.api.download_packing_labels?job=${encodeURIComponent(job)}`;
	window.open(url, "_blank");
};

window.elemental_download_job_label_pdf = function (job, method) {
	if (!job) {
		frappe.msgprint("Select a Job first.");
		return;
	}
	window.open(
		`/api/method/elemental_erp.api.${method}?job=${encodeURIComponent(job)}`,
		"_blank"
	);
};

window.elemental_print_job_format = function (job, format) {
	const url =
		`/printview?doctype=Job&name=${encodeURIComponent(job)}` +
		`&format=${encodeURIComponent(format)}&no_letterhead=1`;
	window.open(url, "_blank");
};

frappe.ui.form.on("Job", {
	refresh(frm) {
		if (frm.is_new()) return;

		const isTerminal = frm.doc.status === "Closed" || frm.doc.status === "Cancelled";
		const canPrintPackingLabels = [
			"System Manager",
			"Elemental Packaging User",
			"Elemental Packaging HOD",
			"Elemental Dispatch HOD",
		].some((role) => (frappe.user_roles || []).includes(role));
		const canPrintProductionLabels = [
			"System Manager",
			"Elemental Data Entry User",
			"Elemental Data Entry HOD",
			"Elemental Production User",
			"Elemental Production HOD",
			"Elemental QC User",
			"Elemental QC HOD",
			"Elemental Packaging User",
			"Elemental Packaging HOD",
		].some((role) => (frappe.user_roles || []).includes(role));
		const canPrintFGLabels = [
			"System Manager",
			"Elemental QC User",
			"Elemental QC HOD",
			"Elemental Packaging HOD",
		].some((role) => (frappe.user_roles || []).includes(role));
		const canPrintSubpartLabels = [
			"System Manager",
			"Elemental Data Entry User",
			"Elemental Data Entry HOD",
			"Elemental Production User",
			"Elemental Production HOD",
			"Elemental Packaging User",
			"Elemental Packaging HOD",
		].some((role) => (frappe.user_roles || []).includes(role));
		if (canPrintProductionLabels || canPrintPackingLabels) {
			frm.add_custom_button("Label Print Center", () => {
				frappe.route_options = { job: frm.doc.name };
				frappe.set_route("label-print-center");
			}).addClass("btn-primary");
		}
		if (canPrintPackingLabels) {
			frm.add_custom_button(
				"Print All Packing Labels",
				() => window.elemental_print_all_packing_labels(frm.doc.name),
				"Bulk Print Labels"
			).addClass("btn-primary");
		}
		frm.add_custom_button(
			"Print Job QR Label",
			() => window.elemental_print_job_format(frm.doc.name, "Job QR Label"),
			"Bulk Print Labels"
		);
		frm.add_custom_button(
			"Print Production Traveller",
			() => {
				const printWindow = window.open("about:blank", "_blank");
				frappe.call({
					method: "elemental_erp.api.prepare_job_production_traveller",
					args: { job: frm.doc.name },
					freeze: true,
					freeze_message: "Preparing diagrams and subpart QR labels...",
					callback: (response) => {
						if (response.message) {
							if (printWindow) printWindow.location = response.message.print_url;
							else window.location = response.message.print_url;
						}
					},
					error: () => {
						if (printWindow) printWindow.close();
					},
				});
			},
			"Bulk Print Labels"
		);
		if (canPrintProductionLabels) {
			frm.add_custom_button(
				"Print Job + All FG + Subpart Labels",
				() => window.elemental_print_job_format(frm.doc.name, "Job All Production QR Labels"),
				"Bulk Print Labels"
			).addClass("btn-primary");
			if (canPrintFGLabels) {
				frm.add_custom_button(
					"Print All FG / QC Labels",
					() => window.elemental_download_job_label_pdf(frm.doc.name, "download_job_fg_labels"),
					"Bulk Print Labels"
				);
			}
			if (canPrintSubpartLabels) {
				frm.add_custom_button(
					"Print All Subpart Labels",
					() => window.elemental_download_job_label_pdf(frm.doc.name, "download_job_subpart_labels"),
					"Bulk Print Labels"
				);
			}
		}

		if (isTerminal) {
			frm.set_intro(
				`This Job is ${frm.doc.status} and locked from further edits.`,
				frm.doc.status === "Closed" ? "green" : "red"
			);
			frm.add_custom_button("Reopen Job", () => {
				frappe.confirm(
					`Reopen this ${frm.doc.status} Job? Only do this if it genuinely needs further work.`,
					() => {
						frappe.call({
							method: "elemental_erp.api.reopen_job",
							args: { job: frm.doc.name },
							callback: () => frm.reload_doc(),
						});
					}
				);
			}).addClass("btn-primary");
			return; // no other actions make sense on a locked Job
		}

		frm.add_custom_button(
			"View QR Codes",
			() => frappe.set_route("List", "QR Code Master", { job: frm.doc.name }),
			"View"
		);
		frm.add_custom_button(
			"View Subpart Labels",
			() => frappe.set_route("List", "Job Subpart Label", { job: frm.doc.name }),
			"View"
		);
		frm.add_custom_button(
			"Job Consumption Report",
			() => frappe.set_route("query-report", "Job Consumption Report", { job: frm.doc.name }),
			"View"
		);
		frm.add_custom_button(
			"View Packing Boxes",
			() => frappe.set_route("List", "Packing Box", { job: frm.doc.name }),
			"View"
		);
		frm.add_custom_button(
			"View Design Tasks",
			() => frappe.set_route("List", "Design Task", { job: frm.doc.name }),
			"View"
		);

		frm.add_custom_button(
			"New Material Indent",
			() => frappe.new_doc("Material Indent", { job: frm.doc.name }),
			"Create"
		);
		frm.add_custom_button(
			"New Material Issue",
			() => frappe.new_doc("Material Issue", { job: frm.doc.name }),
			"Create"
		);

		frm.add_custom_button(
			"Complete Data Entry Task",
			() => {
				frappe.prompt(
					[
						{ fieldname: "hours_spent", label: "Hours Spent", fieldtype: "Float" },
						{ fieldname: "remarks", label: "Remarks", fieldtype: "Small Text" },
					],
					(values) => {
						frappe.call({
							method: "elemental_erp.api.complete_data_entry_task",
							args: { job: frm.doc.name, hours_spent: values.hours_spent, remarks: values.remarks },
							callback: () => frappe.show_alert("Data Entry Task marked completed."),
						});
					},
					"Complete Data Entry Task"
				);
			},
			"Create"
		);

		frm.add_custom_button(
			"Create Sales Invoice",
			() => {
				frappe.call({
					method: "elemental_erp.api.create_sales_invoice_for_job",
					args: { job: frm.doc.name },
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
			"Create"
		);

		if (!frm.doc.packaging_completed) {
			frm.add_custom_button("Mark Packaging Completed \u2192 Consume Material", () => {
				frappe.confirm(
					"This rolls up EVERY department's issued material for this Job into one " +
						"Job Material Consumption draft, for costing to review. Continue?",
					() => {
						frappe.call({
							method: "elemental_erp.api.mark_job_packaging_completed",
							args: { job: frm.doc.name },
							callback: (r) => {
								if (r.message) {
									frappe.show_alert(
										`Job Material Consumption ${r.message.job_material_consumption} created (Draft).`
									);
									frm.reload_doc();
								}
							},
						});
					}
				);
			}).addClass("btn-warning");
		}

		frm.add_custom_button(
			"Create Packing Box Labels",
			() => {
				frappe.prompt(
					{
						fieldname: "total_boxes",
						label: "How many boxes/labels?",
						fieldtype: "Int",
						reqd: 1,
						default: frm.doc.total_packing_boxes,
					},
					(values) => {
						frappe.call({
							method: "elemental_erp.api.create_packing_labels",
							args: { job: frm.doc.name, total_boxes: values.total_boxes },
							callback: (r) => {
								if (r.message) {
									frappe.show_alert(`${r.message.created} box labels created.`);
									frappe.set_route("List", "Packing Box", { job: frm.doc.name });
								}
							},
						});
					},
					"Create Packing Labels"
				);
			},
			"Create"
		);

		// --- terminal actions, kept visually separate ---
		frm.add_custom_button(
			"Close Job",
			() => {
				frappe.confirm(
					"Mark this Job Closed? It will be locked from further edits. Use this only if " +
						"the Job is genuinely done and didn't go through the box-by-box install " +
						"confirmation (see /site-scan) already.",
					() => {
						frappe.call({
							method: "elemental_erp.api.close_job",
							args: { job: frm.doc.name },
							callback: () => frm.reload_doc(),
						});
					}
				);
			},
			"Status"
		);
		frm.add_custom_button(
			"Cancel Job",
			() => {
				frappe.prompt(
					{ fieldname: "reason", label: "Reason", fieldtype: "Small Text", reqd: 1 },
					(values) => {
						frappe.confirm(
							"This cancels every submittable record against this Job (Indents, Issues, " +
								"Production/Packaging/Dispatch Entries, Material Consumption). This cannot " +
								"be undone by reopening. Continue?",
							() => {
								frappe.call({
									method: "elemental_erp.api.cancel_job",
									args: { job: frm.doc.name, reason: values.reason },
									callback: () => frm.reload_doc(),
								});
							}
						);
					},
					"Cancel Job"
				);
			},
			"Status"
		);
	},
});
