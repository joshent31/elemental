const elemental_fg_process_fields = [
	["process_metal", "Metal"],
	["process_wood", "Wood"],
	["process_electrical", "Electrical"],
	["process_powdercoating", "Powdercoating"],
	["process_paint", "Paint"],
	["process_us_assembly", "US Assembly"],
	["process_packing", "Packing"],
];

function elemental_update_fg_process_flow(cdt, cdn) {
	const row = locals[cdt][cdn];
	const selected = elemental_fg_process_fields
		.filter(([fieldname]) => Boolean(row[fieldname]))
		.map(([, label]) => label);
	frappe.model.set_value(cdt, cdn, "process_flow", selected.join(" → "));
	frappe.model.set_value(cdt, cdn, "processes", selected.join("\n"));
}

const elemental_fg_process_handlers = {};
for (const [fieldname] of elemental_fg_process_fields) {
	elemental_fg_process_handlers[fieldname] = (_frm, cdt, cdn) => {
		elemental_update_fg_process_flow(cdt, cdn);
	};
}

elemental_fg_process_handlers.subparts_add = (_frm, cdt, cdn) => {
	const row = locals[cdt][cdn];
	if (row.part_code) return;
	frappe.call({
		method:
			"elemental_erp.elemental_erp.doctype.finished_good.finished_good.get_next_part_code",
		callback: (response) => {
			if (response.message && !locals[cdt][cdn].part_code) {
				frappe.model.set_value(cdt, cdn, "part_code", response.message);
			}
		},
	});
};

frappe.ui.form.on("FG Subpart", elemental_fg_process_handlers);

function elemental_calculate_bom_qty(cdt, cdn) {
	const row = locals[cdt][cdn];
	const pcs = flt(row.pieces || 0);
	const factor = flt(row.conversion_factor || 0);
	let base_qty = 0;
	if (row.calculation_basis === "Pieces") base_qty = pcs;
	if (row.calculation_basis === "Length") base_qty = flt(row.length_mm) * pcs;
	if (row.calculation_basis === "Area") base_qty = flt(row.length_mm) * flt(row.width_mm) * pcs;
	if (row.calculation_basis === "Volume") base_qty = flt(row.length_mm) * flt(row.width_mm) * flt(row.height_mm) * pcs;
	if (row.calculation_basis !== "Manual" && factor > 0) {
		frappe.model.set_value(cdt, cdn, "qty_per_fg", flt(base_qty / factor, 6));
	}
}

frappe.ui.form.on("FG BOM Item", {
	raw_material(_frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.raw_material) return;
		frappe.db.get_value("Item", row.raw_material, [
			"stock_uom", "elemental_fg_consumption_basis", "elemental_fg_conversion_factor",
		]).then(({ message }) => {
			frappe.model.set_value(cdt, cdn, {
				uom: message.stock_uom,
				calculation_basis: message.elemental_fg_consumption_basis || "Manual",
				conversion_factor: flt(message.elemental_fg_conversion_factor || 1),
			}).then(() => elemental_calculate_bom_qty(cdt, cdn));
		});
	},
	length_mm: (_frm, cdt, cdn) => elemental_calculate_bom_qty(cdt, cdn),
	width_mm: (_frm, cdt, cdn) => elemental_calculate_bom_qty(cdt, cdn),
	height_mm: (_frm, cdt, cdn) => elemental_calculate_bom_qty(cdt, cdn),
	pieces: (_frm, cdt, cdn) => elemental_calculate_bom_qty(cdt, cdn),
});
