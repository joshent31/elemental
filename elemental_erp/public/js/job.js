// Client script for the Job form. Job is NOT submittable — it stays open
// so new Finished Goods can be added by the customer at any point, right
// up until it's explicitly Closed (or Cancelled). Action buttons are
// gated on "!frm.is_new()", not docstatus (Job has no submit lifecycle),
// and disappear once the Job reaches a terminal status.

frappe.ui.form.on("Job", {
	refresh(frm) {
		if (frm.is_new()) return;

		const isTerminal = frm.doc.status === "Closed" || frm.doc.status === "Cancelled";

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
