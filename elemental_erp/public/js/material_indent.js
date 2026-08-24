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
				frm.add_custom_button("Open Purchase Order", () => {
					frappe.set_route("Form", "Purchase Order", frm.doc.purchase_order);
				}, "View");
			}

			const canPurchase = ["System Manager", "Elemental Purchase User", "Elemental Purchase HOD"].some(
				(role) => (frappe.user_roles || []).includes(role)
			);
			const hasShortfall = (frm.doc.items || []).some((row) => (row.shortfall_qty || 0) > 0);
			if (canPurchase && hasShortfall) {
				frm.add_custom_button("Open PO Initiation", () => {
					frappe.route_options = { job: frm.doc.job };
					frappe.set_route("po-initiation");
				}, "Purchase").addClass("btn-primary");

				frm.add_custom_button("New Purchase Order", () => {
					frappe.new_doc("Purchase Order", {
						elemental_job: frm.doc.job,
						elemental_material_indent: frm.doc.name,
					});
				}, "Purchase");
			}
		}
	},
});
