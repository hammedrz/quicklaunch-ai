"""Tests for local system tools."""
import pytest
from src.ai.tools.system_tools import calculate, get_system_info


def test_calculate_basic_math():
    assert calculate("2 + 3") == "5"


def test_calculate_sqrt():
    assert calculate("sqrt(144)") == "12.0"


def test_calculate_power():
    assert calculate("2^10") == "1024"


def test_calculate_pi():
    result = float(calculate("pi"))
    assert abs(result - 3.14159265) < 0.001


def test_calculate_complex_expression():
    result = float(calculate("sin(pi/2) * 100"))
    assert abs(result - 100.0) < 0.001


def test_calculate_disallowed_name():
    result = calculate("__import__('os')")
    assert "Error" in result


def test_calculate_invalid_expression():
    result = calculate("definitely not math !!!")
    assert "Error" in result


def test_get_system_info_returns_string():
    info = get_system_info()
    assert isinstance(info, str)
    assert "OS:" in info
    assert "RAM:" in info
    assert "Primary Disk:" in info
