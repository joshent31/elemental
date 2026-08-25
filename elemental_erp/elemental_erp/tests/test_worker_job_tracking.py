"""Static regression checks for supervisor worker-to-Job time tracking."""

import ast
import json
from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[2]
WORKER_JOB_API = APP_ROOT / "worker_job.py"
WORKSTATION = APP_ROOT / "elemental_erp" / "doctype" / "production_workstation" / "production_workstation.json"
TIME_LOG = APP_ROOT / "elemental_erp" / "doctype" / "worker_job_time_log" / "worker_job_time_log.json"
MOBILE_PAGE = APP_ROOT / "templates" / "pages" / "worker_job_scan.html"
GATE_API = APP_ROOT / "api.py"
JOB_REPORT = APP_ROOT / "elemental_erp" / "report" / "job_consumption_report" / "job_consumption_report.py"


class TestWorkerJobTracking(unittest.TestCase):
	def test_doctypes_capture_qr_time_cost_and_audit(self):
		workstation = json.loads(WORKSTATION.read_text(encoding="utf-8"))
		log = json.loads(TIME_LOG.read_text(encoding="utf-8"))
		self.assertEqual(workstation["image_field"], "qr_image")
		workstation_fields = {field["fieldname"] for field in workstation["fields"]}
		self.assertTrue({"qr_value", "qr_image", "department", "status"}.issubset(workstation_fields))
		log_fields = {field["fieldname"] for field in log["fields"]}
		self.assertTrue({"employee", "job", "workstation", "start_time", "end_time", "hours_spent", "hourly_rate", "labour_cost", "started_by", "closed_by", "active_employee_key"}.issubset(log_fields))
		active_key = next(field for field in log["fields"] if field["fieldname"] == "active_employee_key")
		self.assertEqual(active_key.get("unique"), 1)

	def test_supervisor_api_enforces_gate_in_and_single_active_job(self):
		source = WORKER_JOB_API.read_text(encoding="utf-8")
		for expected in (
			"_require_gate_in",
			"status = 'Active' FOR UPDATE",
			"already has active allocation",
			"hourly_rate(employee.name",
			"Gate-Out Closed",
			"time_diff_in_seconds",
		):
			self.assertIn(expected, source)
		tree = ast.parse(source)
		functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
		for name in ("lookup_workstation", "lookup_worker", "lookup_job", "start_workers", "close_workers", "get_active_allocations"):
			calls = [node for node in ast.walk(functions[name]) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_require_supervisor"]
			self.assertTrue(calls, f"{name} must enforce supervisor permission")

	def test_mobile_page_has_start_hold_and_complete_flow(self):
		source = MOBILE_PAGE.read_text(encoding="utf-8")
		for expected in ("Machine / Table QR", "Job QR", "Worker Employee QR", "Start Job", "Hold Selected", "Complete Selected"):
			self.assertIn(expected, source)

	def test_gate_out_closes_open_time_and_job_cost_includes_logs(self):
		self.assertIn("close_active_logs_for_gate_out", GATE_API.read_text(encoding="utf-8"))
		report = JOB_REPORT.read_text(encoding="utf-8")
		self.assertIn("tabWorker Job Time Log", report)
		self.assertIn("worker_job.cost", report)


if __name__ == "__main__":
	unittest.main()
