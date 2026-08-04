"""Tests for utils/ci/gitlab/matrix.py — parsing of the per-library MATRIX variable."""

import pytest

from utils import scenarios
from utils.ci.gitlab.matrix import parse_matrix


@scenarios.test_the_test
class Test_ParseMatrix:
    def test_empty_string(self):
        assert parse_matrix("") == {}

    def test_blank_string(self):
        assert parse_matrix("   \n  ") == {}

    def test_example_from_prompt(self):
        matrix = "{python: {scenarios: [DEFAULT, FOO]}, python_lambda: {scenario_groups: tracer_release}}"
        assert parse_matrix(matrix) == {
            "python": {"scenarios": "DEFAULT,FOO"},
            "python_lambda": {"scenario_groups": "tracer_release"},
        }

    def test_single_scalar_value_without_brackets(self):
        assert parse_matrix("{python: {scenario_groups: tracer_release}}") == {
            "python": {"scenario_groups": "tracer_release"}
        }

    def test_multiple_keys_per_library(self):
        matrix = "{python: {scenarios: [DEFAULT, FOO], weblogs: [flask, django-poetry]}}"
        assert parse_matrix(matrix) == {
            "python": {"scenarios": "DEFAULT,FOO", "weblogs": "flask,django-poetry"},
        }

    def test_excluded_scenarios_key(self):
        matrix = "{python: {excluded_scenarios: [FOO]}}"
        assert parse_matrix(matrix) == {"python": {"excluded_scenarios": "FOO"}}

    def test_unknown_field_raises(self):
        with pytest.raises(ValueError, match="unknown key"):
            parse_matrix("{python: {not_a_field: [DEFAULT]}}")

    def test_not_a_mapping_raises(self):
        with pytest.raises(TypeError, match="expected a mapping"):
            parse_matrix("[python, java]")

    def test_library_config_not_a_mapping_raises(self):
        with pytest.raises(TypeError, match="must be a mapping"):
            parse_matrix("{python: DEFAULT}")

    def test_invalid_yaml_raises(self):
        with pytest.raises(ValueError, match="not valid YAML"):
            parse_matrix("{python: {scenarios: [DEFAULT, FOO}}")
