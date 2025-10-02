"""Basic tests for the Open Soup Rating package."""

import pytest
import open_soup_rating as osr


def test_package_import():
    """Test that the package imports correctly."""
    assert osr.__version__ == "1.1.1"
    assert osr.__author__ == "Zach Lewis"
    assert osr.__license__ == "AGPL-3.0"


def test_list_components():
    """Test that list_components works."""
    components = osr.list_components()
    assert isinstance(components, list)
    assert len(components) > 0
    # Should contain core components
    expected_components = {'KillContrib', 'DeathContrib', 'APR', 'ADRa'}
    assert expected_components.issubset(set(components))


def test_core_functions_exist():
    """Test that core functions are available."""
    assert hasattr(osr, 'calculate_rating')
    assert hasattr(osr, 'calculate_rating_with_player_info')
    assert hasattr(osr, 'get_components')
    assert hasattr(osr, 'load_match_data')
    assert hasattr(osr, 'load_config_data')


def test_component_management():
    """Test component registry functions."""
    assert hasattr(osr, 'add_component')
    assert hasattr(osr, 'remove_component')
    assert hasattr(osr, 'list_components')