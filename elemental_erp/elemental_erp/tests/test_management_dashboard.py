"""Regression checks for the Management Dashboard's Frappe v15 client API usage."""

from pathlib import Path
import unittest


DASHBOARD_JS = (
	Path(__file__).resolve().parents[1]
	/ "page"
	/ "management_dashboard"
	/ "management_dashboard.js"
).read_text(encoding="utf-8")


class TestManagementDashboardClient(unittest.TestCase):
	def test_uses_frappe_v15_currency_formatter(self):
		self.assertIn("format_currency(stats.total_revenue || 0)", DASHBOARD_JS)
		self.assertNotIn("frappe.format.currency_with_symbol", DASHBOARD_JS)

	def test_refresh_button_is_not_treated_as_a_button_group(self):
		self.assertIn(
			'this.page.add_inner_button("Refresh", () => this.load_all(), null, "primary")',
			DASHBOARD_JS,
		)

	def test_failed_requests_replace_loading_placeholders(self):
		self.assertIn("error: () => this.render_error()", DASHBOARD_JS)
		self.assertIn("Unable to load dashboard data", DASHBOARD_JS)

	def test_empty_or_zero_chart_data_is_not_sent_to_svg_renderer(self):
		self.assertIn("const render_or_empty", DASHBOARD_JS)
		self.assertIn("Number.isFinite(value) && value !== 0", DASHBOARD_JS)
		self.assertIn("No chart data for this period", DASHBOARD_JS)
		self.assertNotIn("frappe.query_report = frappe.query_report || {}", DASHBOARD_JS)


if __name__ == "__main__":
	unittest.main()
