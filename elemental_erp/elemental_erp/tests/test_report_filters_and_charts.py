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


class TestReportFiltersAndCharts(unittest.TestCase):
	def setUp(self):
		self.report_root = Path(__file__).resolve().parents[1] / "report"

	def test_every_report_has_month_and_year_filters(self):
		for report in REPORTS:
			with self.subTest(report=report):
				source = (self.report_root / report / f"{report}.js").read_text(encoding="utf-8")
				self.assertIn('fieldname: "month"', source)
				self.assertIn('fieldname: "year"', source)

	def test_every_report_defines_a_chart(self):
		for report in REPORTS:
			with self.subTest(report=report):
				path = self.report_root / report / f"{report}.py"
				tree = ast.parse(path.read_text(encoding="utf-8"))
				functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
				self.assertIn("get_chart", functions)


if __name__ == "__main__":
	unittest.main()
