frappe.ui.form.on("Elemental Quotation", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.docstatus === 1 && frm.doc.status === "Sent to Customer") {
			frm.add_custom_button("Mark Approved by Customer", () => {
				frappe.prompt(
					{
						fieldname: "approval_reference",
						label: "Approval Reference (email subject/thread, call note, etc.)",
						fieldtype: "Data",
						reqd: 1,
					},
					(values) => {
						frappe.call({
							method: "elemental_erp.api.mark_quotation_approved",
							args: { quotation: frm.doc.name, approval_reference: values.approval_reference },
							callback: () => frm.reload_doc(),
						});
					},
					"Customer Approval"
				);
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Approved by Customer" && !frm.doc.job) {
			frm.add_custom_button("Create Job from Quotation", () => {
				frappe.confirm(
					"Create a Job from this Quotation now? Production can start on the strength of " +
						"this approval \u2014 the formal PO can be logged on the Job later, whenever it " +
						"actually arrives.",
					() => {
						frappe.call({
							method: "elemental_erp.api.create_job_from_quotation",
							args: { quotation: frm.doc.name },
							callback: (r) => {
								if (r.message) {
									frappe.set_route("Form", "Job", r.message.job);
								}
							},
						});
					}
				);
			}).addClass("btn-warning");
		}

		if (frm.doc.job) {
			frm.add_custom_button("View Job", () => {
				frappe.set_route("Form", "Job", frm.doc.job);
			}, "View");
		}
	},
});
