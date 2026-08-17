frappe.ui.form.on("Material Indent", {
	refresh(frm) {
		if (frm.is_new() && frm.doc.job) {
			frm.add_custom_button("Pull Items from Job BOM", () => {
				frappe.call({
					method: "elemental_erp.api.generate_indent_items_from_bom",
					args: { job: frm.doc.job },
					callback: (r) => {
						if (r.message) {
							r.message.items.forEach((row) => {
								const child = frm.add_child("items");
								child.raw_material = row.raw_material;
								child.uom = row.uom;
								child.required_qty = row.required_qty;
							});
							frm.set_value("raised_by", "Costing (BOM)");
							frm.set_value("covered_finished_goods", JSON.stringify(r.message.covered_finished_goods || []));
							frm.refresh_field("items");
							frappe.show_alert(`Pulled ${r.message.items.length} material line(s) from the BOM.`);
						}
					},
				});
			});
		}

		if (!frm.is_new() && frm.doc.docstatus === 1) {
			if (frm.doc.purchase_order) {
				// Draft PO was already auto-created when this Indent was
				// approved — jump straight to it to add a supplier / rates.
				frm.add_custom_button("Open Purchase Order", () => {
					frappe.set_route("Form", "Purchase Order", frm.doc.purchase_order);
				}, "View");
			} else {
				const hasShortfall = (frm.doc.items || []).some((row) => (row.shortfall_qty || 0) > 0);
				if (hasShortfall) {
					frm.add_custom_button("Create Purchase Order (Shortfall)", () => {
						frappe.prompt(
							{
								fieldname: "supplier",
								label: "Supplier (existing name, or type a new vendor name)",
								fieldtype: "Data",
								description: "Matches an existing Supplier if the name exists, otherwise creates a new one.",
							},
							(values) => {
								frappe.call({
									method: "elemental_erp.api.create_purchase_order_from_indent",
									args: { material_indent: frm.doc.name, supplier: values.supplier },
									callback: (r) => {
										if (r.message) {
											frappe.show_alert(`Draft Purchase Order ${r.message.purchase_order} created.`);
											frm.reload_doc();
										}
									},
								});
							},
							"Create Purchase Order"
						);
					}).addClass("btn-primary");
				}
			}
		}
	},
});
