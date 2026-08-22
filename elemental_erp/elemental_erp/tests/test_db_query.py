"""Regression tests for database-query compatibility helpers."""

import unittest

from elemental_erp.utils.db_query import strip_doctype_table_prefix


class TestStripDoctypeTablePrefix(unittest.TestCase):
	doctype = "Work from Home Request"

	def test_strips_backtick_and_double_quote_prefixes(self):
		self.assertEqual(
			strip_doctype_table_prefix("`tabWork from Home Request`.`name`", self.doctype),
			"`name`",
		)
		self.assertEqual(
			strip_doctype_table_prefix('"tabWork from Home Request"."name"', self.doctype),
			'"name"',
		)

	def test_strips_prefix_inside_supported_aggregate(self):
		self.assertEqual(
			strip_doctype_table_prefix(
				"count(`tabWork from Home Request`.`name`) as total_count",
				self.doctype,
			),
			"count(`name`) as total_count",
		)

	def test_keeps_other_tables_and_security_sensitive_text(self):
		self.assertEqual(
			strip_doctype_table_prefix("`tabEmployee`.`employee_name`", self.doctype),
			"`tabEmployee`.`employee_name`",
		)
		self.assertEqual(
			strip_doctype_table_prefix("name, sleep(1)", self.doctype),
			"name, sleep(1)",
		)

	def test_preserves_none_and_simple_fields(self):
		self.assertIsNone(strip_doctype_table_prefix(None, self.doctype))
		self.assertEqual(strip_doctype_table_prefix("name", self.doctype), "name")
