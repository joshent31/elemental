frappe.pages["management-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Elemental — Management Dashboard",
		single_column: true,
	});

	new ManagementDashboard(page);
};

class ManagementDashboard {
	constructor(page) {
		this.page = page;
		this.make_header();
		this.make_stats_row();
		this.make_charts_row();
		this.make_recent_jobs();
		this.load_all();
	}

	make_header() {
		this.page.add_inner_button("Refresh", () => this.load_all(), "btn-primary");
	}

	make_stats_row() {
		this.$stats = $(`
			<div class="row" style="margin: 0 -10px 18px;" id="dash-stats"></div>
		`).appendTo(this.page.body);
	}

	make_charts_row() {
		this.$charts = $(`
			<div class="row" style="margin: 0 -10px 18px;">
				<div class="col-md-4" id="dash-chart-status" style="margin-bottom:16px;"></div>
				<div class="col-md-4" id="dash-chart-monthly" style="margin-bottom:16px;"></div>
				<div class="col-md-4" id="dash-chart-department" style="margin-bottom:16px;"></div>
			</div>
		`).appendTo(this.page.body);
	}

	make_recent_jobs() {
		this.$recent = $(`
			<div style="margin-bottom:16px;">
				<h5 style="margin-bottom:10px;">Recent Jobs</h5>
				<div id="dash-recent-jobs"></div>
			</div>
		`).appendTo(this.page.body);
	}

	load_all() {
		this.$stats.empty().html('<div class="text-muted" style="padding:20px;">Loading…</div>');
		this.$recent.find("#dash-recent-jobs").html('<div class="text-muted">Loading…</div>');

		frappe.call({
			method: "elemental_erp.api.get_dashboard_data",
			freeze: true,
			callback: (r) => {
				if (r.message) {
					this.render_stats(r.message.stats);
					this.render_charts(r.message.charts);
					this.render_recent_jobs(r.message.recent_jobs);
				}
			},
		});
	}

	render_stats(stats) {
		const cards = [
			{ label: "Active Jobs", value: stats.active_jobs, color: "#2490ef", icon: "fa-briefcase" },
			{ label: "In Production", value: stats.in_production, color: "#7b61ff", icon: "fa-cogs" },
			{ label: "Pending Indents", value: stats.pending_indents, color: "#ff5858", icon: "fa-file-text-o" },
			{ label: "QR Completion", value: stats.qr_completion_pct + "%", color: "#28a745", icon: "fa-check-circle" },
			{ label: "Total Revenue", value: frappe.format.currency_with_symbol(stats.total_revenue), color: "#f0ad4e", icon: "fa-rupee" },
			{ label: "Total Cost", value: frappe.format.currency_with_symbol(stats.total_cost), color: "#dc3545", icon: "fa-calculator" },
			{ label: "Avg Margin", value: stats.avg_margin_pct + "%", color: stats.avg_margin_pct >= 0 ? "#28a745" : "#dc3545", icon: "fa-line-chart" },
			{ label: "Overdue Jobs", value: stats.overdue_jobs, color: stats.overdue_jobs > 0 ? "#dc3545" : "#28a745", icon: "fa-exclamation-triangle" },
		];

		let html = "";
		cards.forEach((c) => {
			html += `
				<div class="col-md-3" style="margin-bottom:12px;">
					<div style="background:#fff; border-radius:8px; padding:16px; border-left:4px solid ${c.color}; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
						<div style="display:flex; align-items:center; justify-content:space-between;">
							<div>
								<div style="font-size:12px; color:#888; text-transform:uppercase; letter-spacing:0.5px;">${c.label}</div>
								<div style="font-size:26px; font-weight:700; color:#333; margin-top:4px;">${c.value}</div>
							</div>
							<i class="fa ${c.icon}" style="font-size:28px; color:${c.color}; opacity:0.3;"></i>
						</div>
					</div>
				</div>
			`;
		});
		this.$stats.html(html);
	}

	render_charts(charts) {
		// Chart 1: Jobs by Status (Pie)
		frappe.query_report = frappe.query_report || {};
		new frappe.Chart("#dash-chart-status", {
			title: "Jobs by Status",
			type: "pie",
			data: {
				labels: charts.jobs_by_status.map((d) => d.label),
				datasets: [{ values: charts.jobs_by_status.map((d) => d.value) }],
			},
			colors: ["#2490ef", "#7b61ff", "#ff5858", "#f0ad4e", "#28a745", "#17a2b8", "#6f42c1", "#fd7e14", "#20c997", "#e83e8c", "#343a40", "#6c757d"],
		});

		// Chart 2: Monthly Jobs (Bar)
		const monthLabels = charts.monthly_jobs.map((d) => d.label);
		const monthCreated = charts.monthly_jobs.map((d) => d.created);
		const monthClosed = charts.monthly_jobs.map((d) => d.closed);
		new frappe.Chart("#dash-chart-monthly", {
			title: "Jobs — Last 6 Months",
			type: "bar",
			data: {
				labels: monthLabels,
				datasets: [
					{ name: "Created", values: monthCreated },
					{ name: "Closed", values: monthClosed },
				],
			},
			colors: ["#2490ef", "#28a745"],
			barOptions: { spaceRatio: 0.25 },
		});

		// Chart 3: Department Activity (Bar — horizontal)
		const deptLabels = charts.department_activity.map((d) => d.label);
		const deptValues = charts.department_activity.map((d) => d.value);
		new frappe.Chart("#dash-chart-department", {
			title: "Active Transfers by Department",
			type: "bar",
			data: {
				labels: deptLabels,
				datasets: [{ name: "Pending/In Transit", values: deptValues }],
			},
			colors: ["#ff5858"],
			barOptions: { horizontalBars: true, spaceRatio: 0.25 },
		});
	}

	render_recent_jobs(jobs) {
		if (!jobs || !jobs.length) {
			this.$recent.find("#dash-recent-jobs").html('<div class="text-muted">No jobs found.</div>');
			return;
		}

		const statusColors = {
			"Job Created": "#6c757d",
			"Indent Raised": "#ffc107",
			"In Purchase": "#17a2b8",
			"In Production": "#7b61ff",
			"In Packaging": "#fd7e14",
			"Material Consumption Pending": "#e83e8c",
			"Material Consumed": "#20c997",
			"Dispatched": "#2490ef",
			"Installed": "#28a745",
			"Closed": "#343a40",
			Cancelled: "#dc3545",
		};

		let html = `
			<table class="table table-bordered table-hover" style="font-size:13px;">
				<thead>
					<tr>
						<th>Job</th>
						<th>Customer</th>
						<th>Status</th>
						<th>QR %</th>
						<th>Boxes</th>
						<th>Due Date</th>
						<th></th>
					</tr>
				</thead>
				<tbody>
		`;
		jobs.forEach((j) => {
			const color = statusColors[j.status] || "#6c757d";
			const overdue = j.due_date && j.due_date < frappe.datetime.get_today() && !["Closed", "Cancelled", "Installed"].includes(j.status);
			html += `
				<tr style="${overdue ? "background:#fff5f5;" : ""}">
					<td><a href="/app/job/${j.name}"><b>${j.name}</b></a><br><span class="text-muted">${j.job_name || ""}</span></td>
					<td>${j.customer || ""}</td>
					<td><span class="label" style="background:${color}; color:#fff; font-size:11px;">${j.status}</span></td>
					<td>${j.qr_pct || 0}%</td>
					<td>${j.packed_boxes || 0} / ${j.total_boxes || 0}</td>
					<td style="${overdue ? "color:#dc3545; font-weight:bold;" : ""}">${j.due_date || "—"}</td>
					<td><a href="/app/job/${j.name}" class="btn btn-xs btn-default">Open</a></td>
				</tr>
			`;
		});
		html += "</tbody></table>";
		this.$recent.find("#dash-recent-jobs").html(html);
	}
}
