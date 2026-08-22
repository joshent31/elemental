"""Regression tests for database-query compatibility helpers."""

import unittest
from types import SimpleNamespace

from elemental_erp.utils.db_query import (
	normalize_database_query_fields,
	strip_doctype_table_prefix,
)


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

	def test_normalizes_affected_database_query(self):
		query = SimpleNamespace(
			doctype=self.doctype,
			fields=["`tabWork from Home Request`.`name`", "name, sleep(1)"],
		)
		self.assertTrue(normalize_database_query_fields(query))
		self.assertEqual(query.fields, ["`name`", "name, sleep(1)"])

	def test_does_not_change_other_database_queries(self):
		query = SimpleNamespace(doctype="Employee", fields=["`tabEmployee`.`name`"])
		self.assertFalse(normalize_database_query_fields(query))
		self.assertEqual(query.fields, ["`tabEmployee`.`name`"])
