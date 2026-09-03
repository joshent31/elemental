import ast
import unittest
from pathlib import Path


REPORTS = (
	"job_consumption_report",
	"ot_request_vs_checkout",
	"wfh_summary",
	"worker_attendance_report",
	"worker_checkin_detail",
	"worker_job_cost",
	"worker_ot_summary",
)

EMPLOYEE_REPORTS = tuple(report for report in REPORTS if report != "job_consumption_report")


class TestReportFiltersAndCharts(unittest.TestCase):
	def setUp(self):
		self.report_root = Path(__file__).resolve().parents[1] / "report"

	def test_every_report_has_month_and_year_filters(self):
		for report in REPORTS:
			with self.subTest(report=report):
				source = (self.report_root / report / f"{report}.js").read_text(encoding="utf-8")
				self.assertIn('fieldname: "month"', source)
				self.assertIn('fieldname: "year"', source)
				self.assertIn('"JAN", "FEB", "MAR"', source)
				self.assertIn("value: String(index + 1)", source)

	def test_every_report_defines_a_chart(self):
		for report in REPORTS:
			with self.subTest(report=report):
				path = self.report_root / report / f"{report}.py"
				tree = ast.parse(path.read_text(encoding="utf-8"))
				functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
				self.assertIn("get_chart", functions)

	def test_numeric_charts_skip_empty_all_zero_datasets(self):
		for report in set(REPORTS) - {"ot_request_vs_checkout"}:
			with self.subTest(report=report):
				source = (self.report_root / report / f"{report}.py").read_text(encoding="utf-8")
				self.assertIn("if not any(", source)

	def test_employee_reports_filter_employee_category_in_ui_and_server(self):
		for report in EMPLOYEE_REPORTS:
			with self.subTest(report=report):
				client = (self.report_root / report / f"{report}.js").read_text(encoding="utf-8")
				server = (self.report_root / report / f"{report}.py").read_text(encoding="utf-8")
				self.assertIn('fieldname: "employee_category"', client)
				self.assertIn('filters.get("employee_category")', server)

	def test_worker_times_use_full_datetime_and_24_hour_display(self):
		for report in ("worker_attendance_report", "worker_checkin_detail"):
			with self.subTest(report=report):
				source = (self.report_root / report / f"{report}.py").read_text(encoding="utf-8")
				self.assertIn("get_datetime(dt)", source)
				self.assertIn('strftime("%H:%M")', source)
				self.assertNotIn('strftime("%I:%M', source)

	def test_only_sunday_is_automatic_weekly_off(self):
		paths = (
			Path(__file__).resolve().parents[2] / "utils" / "worker_overtime.py",
			Path(__file__).resolve().parents[2] / "api.py",
			self.report_root / "worker_checkin_detail" / "worker_checkin_detail.py",
			self.report_root / "ot_request_vs_checkout" / "ot_request_vs_checkout.py",
		)
		for path in paths:
			with self.subTest(path=path.name):
				source = path.read_text(encoding="utf-8")
				self.assertIn("weekday() == 6", source)
				self.assertNotIn("weekday() >= 5", source)


if __name__ == "__main__":
	unittest.main()
