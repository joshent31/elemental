frappe.pages["po-initiation"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "PO Initiation \u2014 Purchase Workbench",
		single_column: true,
	});

	wrapper.po_initiation = new POInitiation(page);
};

frappe.pages["po-initiation"].on_page_show = function (wrapper) {
	if (wrapper.po_initiation) wrapper.po_initiation.apply_route_options();
};

class POInitiation {
	constructor(page) {
		this.page = page;
		this.mode = "job"; // "job" or "item_group"
		this.rows = [];
		this.can_place_orders = ["System Manager", "Elemental Purchase User", "Elemental Purchase HOD"].some(
			(role) => (frappe.user_roles || []).includes(role)
		);
		this.make_filters();
		this.make_table_area();
		this.apply_route_options();
	}

	escape(value) {
		return frappe.utils.escape_html(String(value ?? ""));
	}

	make_filters() {
		const $filters = $(`
			<div class="po-init-filters" style="display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap; margin-bottom:16px;">
				<div>
					<label style="font-size:12px; color:#888;">
						<input type="checkbox" id="po-init-against-job" checked> Against Job
					</label>
				</div>
				<div id="po-init-job-wrap" style="min-width:220px;">
					<label style="font-size:12px; color:#888; display:block;">Job</label>
					<div id="po-init-job-field"></div>
				</div>
				<div id="po-init-ig-wrap" style="min-width:220px; display:none;">
					<label style="font-size:12px; color:#888; display:block;">Item Group</label>
					<div id="po-init-ig-field"></div>
				</div>
				<button class="btn btn-primary btn-sm" id="po-init-fetch">Show Details</button>
			</div>
			<div id="po-init-table-wrap"></div>
		`).appendTo(this.page.body);

		this.job_control = frappe.ui.form.make_control({
			df: { fieldtype: "Link", options: "Job", fieldname: "job", placeholder: "Select a Job" },
			parent: $("#po-init-job-field"),
			only_input: true,
			render_input: true,
		});
		this.job_control.refresh();

		this.item_group_control = frappe.ui.form.make_control({
			df: { fieldtype: "Link", options: "Item Group", fieldname: "item_group", placeholder: "Select an Item Group" },
			parent: $("#po-init-ig-field"),
			only_input: true,
			render_input: true,
		});
		this.item_group_control.refresh();

		$("#po-init-against-job").on("change", (e) => {
			this.mode = e.target.checked ? "job" : "item_group";
			$("#po-init-job-wrap").toggle(this.mode === "job");
			$("#po-init-ig-wrap").toggle(this.mode === "item_group");
		});

		$("#po-init-fetch").on("click", () => this.fetch());
	}

	make_table_area() {
		this.$table_wrap = $("#po-init-table-wrap");
	}

	apply_route_options() {
		const options = frappe.route_options || {};
		frappe.route_options = null;
		if (!options.job) return;
		this.mode = "job";
		this.job_control.set_value(options.job);
		setTimeout(() => this.fetch(), 0);
	}

	fetch() {
		const args = {};
		if (this.mode === "job") {
			args.job = this.job_control.get_value();
			if (!args.job) {
				frappe.msgprint("Select a Job first.");
				return;
			}
		} else {
			args.item_group = this.item_group_control.get_value();
			if (!args.item_group) {
				frappe.msgprint("Select an Item Group first.");
				return;
			}
		}

		frappe.call({
			method: "elemental_erp.api.get_po_initiation_data",
			args,
			freeze: true,
			callback: (r) => {
				this.rows = r.message || [];
				this.render_table();
			},
		});
	}

	render_table() {
		if (!this.rows.length) {
			this.$table_wrap.html(
				'<div class="text-muted" style="padding:20px;">Nothing outstanding \u2014 everything indented has already been placed on a Purchase Order.</div>'
			);
			return;
		}

		const showJobCols = this.mode === "job";
		let html = `
			<table class="table table-bordered" style="font-size:12px;">
				<thead>
					<tr>
						<th>#</th><th>Item</th><th>Bal. Indent Qty</th><th>Supplier</th>
						<th>PO Qty</th><th>PO Rate</th><th>Stock</th><th>Expected Stock</th>
						${showJobCols ? "<th>Res. Qty (other Jobs)</th><th>Job Bal Qty</th>" : ""}
						<th>Lead Time</th><th>Place Order</th>
					</tr>
				</thead>
				<tbody>
		`;
		this.rows.forEach((row, i) => {
			const supplierCell = row.suppliers && row.suppliers.length
				? `<option value="">-- select --</option>` +
				  row.suppliers.map((s) =>
					`<option value="${this.escape(s.supplier)}" data-rate="${s.last_rate || 0}" ${s.supplier === row.default_supplier ? "selected" : ""}>
						${this.escape(s.supplier)}${s.supplier_part_no ? " (" + this.escape(s.supplier_part_no) + ")" : ""}
					</option>`
				  ).join("")
				: null;

			html += `
				<tr data-idx="${i}">
					<td>${i + 1}</td>
					<td><b>${this.escape(row.item_code)}</b><br><span class="text-muted">${this.escape(row.item_name)}</span></td>
					<td>${row.bal_indent_qty} ${this.escape(row.uom)}</td>
					<td>
						${supplierCell
							? `<select class="form-control input-sm po-init-supplier-select" data-idx="${i}" style="width:170px;">${supplierCell}</select>`
							: `<div class="po-init-supplier-cell" data-idx="${i}"></div>
							   <div class="text-muted" style="font-size:10px;">No suppliers mapped on this Item \u2014 pick any</div>`
						}
					</td>
					<td><input type="number" class="form-control input-sm po-init-qty" data-idx="${i}" value="${row.bal_indent_qty}" style="width:90px;"></td>
					<td><input type="number" class="form-control input-sm po-init-rate" data-idx="${i}" value="0" style="width:90px;"></td>
					<td>${row.stock_qty}</td>
					<td>${row.expected_stock}</td>
					${showJobCols ? `<td>${row.reserved_qty}</td><td>${row.job_bal_qty}</td>` : ""}
					<td>${row.lead_time_days || "-"}</td>
					<td>${this.can_place_orders
						? `<button class="btn btn-xs btn-primary po-init-place" data-idx="${i}">PO</button>`
						: '<span class="text-muted">Read only</span>'
					}</td>
				</tr>
			`;
		});
		html += "</tbody></table>";
		this.$table_wrap.html(html);

		// items with NO approved suppliers mapped fall back to a generic
		// Link control (searches every Supplier) so Purchase isn't blocked
		// — everything else uses the filtered <select> built above
		this.supplier_controls = {};
		this.rows.forEach((row, i) => {
			if (row.suppliers && row.suppliers.length) return;
			const ctrl = frappe.ui.form.make_control({
				df: { fieldtype: "Link", options: "Supplier", fieldname: `supplier_${i}` },
				parent: this.$table_wrap.find(`.po-init-supplier-cell[data-idx="${i}"]`),
				only_input: true,
				render_input: true,
			});
			ctrl.refresh();
			this.supplier_controls[i] = ctrl;
		});

		// pre-fill the rate box from the default supplier's last known rate,
		// and keep it in sync if the operator switches supplier in the dropdown
		this.rows.forEach((row, i) => {
			const $select = this.$table_wrap.find(`.po-init-supplier-select[data-idx="${i}"]`);
			if (!$select.length) return;
			const applyRate = () => {
				const rate = $select.find("option:selected").data("rate") || 0;
				this.$table_wrap.find(`.po-init-rate[data-idx="${i}"]`).val(rate);
			};
			applyRate();
			$select.on("change", applyRate);
		});

		this.$table_wrap.find(".po-init-place").on("click", (e) => this.place_order($(e.currentTarget).data("idx")));
	}

	get_supplier_for_row(idx) {
		const $select = this.$table_wrap.find(`.po-init-supplier-select[data-idx="${idx}"]`);
		if ($select.length) return $select.val();
		return this.supplier_controls[idx] ? this.supplier_controls[idx].get_value() : null;
	}

	place_order(idx) {
		const row = this.rows[idx];
		const supplier = this.get_supplier_for_row(idx);
		const qty = this.$table_wrap.find(`.po-init-qty[data-idx="${idx}"]`).val();
		const rate = this.$table_wrap.find(`.po-init-rate[data-idx="${idx}"]`).val();

		if (!supplier) {
			frappe.msgprint("Set a Supplier for this item first.");
			return;
		}

		frappe.call({
			method: "elemental_erp.api.create_po_from_initiation",
			args: {
				rows: [{ item_code: row.item_code, supplier, po_qty: qty, rate }],
				job: this.mode === "job" ? this.job_control.get_value() : null,
			},
			freeze: true,
			callback: (r) => {
				if (r.message) {
					frappe.show_alert(`Draft Purchase Order ${r.message.purchase_orders.join(", ")} created.`);
					this.$table_wrap.find(`tr[data-idx="${idx}"]`).css("opacity", "0.4");
					this.$table_wrap.find(`.po-init-place[data-idx="${idx}"]`).prop("disabled", true).text("Placed");
				}
			},
		});
	}
}
