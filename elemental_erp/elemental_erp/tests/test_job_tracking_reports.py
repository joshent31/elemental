import json
import pathlib
import unittest


REPORT_ROOT = pathlib.Path(__file__).resolve().parents[1] / "report"


class TestJobTrackingReports(unittest.TestCase):
	def test_report_metadata_is_valid(self):
		for folder, name, reference in (
			("job_fg_department_tracker", "Job FG Department Tracker", "QR Code Master"),
			("job_completion", "Job Completion", "Job"),
		):
			metadata = json.loads((REPORT_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8"))
			self.assertEqual(metadata["name"], name)
			self.assertEqual(metadata["report_type"], "Script Report")
			self.assertEqual(metadata["ref_doctype"], reference)

	def test_reports_have_month_names_and_charts(self):
		for folder in ("job_fg_department_tracker", "job_completion"):
			javascript = (REPORT_ROOT / folder / f"{folder}.js").read_text(encoding="utf-8")
			python = (REPORT_ROOT / folder / f"{folder}.py").read_text(encoding="utf-8")
			self.assertIn('"JAN"', javascript)
			self.assertIn('"DEC"', javascript)
			self.assertIn('"type": "bar"', python)
			self.assertIn("return None", python)
			self.assertIn("data, None, _chart(data), _summary(data)", python)

	def test_completion_is_quantity_weighted(self):
		python = (REPORT_ROOT / "job_completion" / "job_completion.py").read_text(encoding="utf-8")
		self.assertIn("completed / total * 100", python)
		self.assertIn("min(flt(tracker.completed_qty), total)", python)

	def test_department_tracker_uses_latest_transfer(self):
		python = (REPORT_ROOT / "job_fg_department_tracker" / "job_fg_department_tracker.py").read_text(encoding="utf-8")
		self.assertIn('order_by="creation asc"', python)
		self.assertIn('"status": ["!=", "Cancelled"]', python)
		self.assertIn("movement.to_department", python)
