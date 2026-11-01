"""Basic tests for the Open Soup Rating package."""

from pathlib import Path

import pytest
import open_soup_rating as osr


def test_package_import():
    """Test that the package imports correctly."""
    assert osr.__version__ == "2.1.0"
    assert osr.__author__ == "Zach Lewis"
    assert osr.__license__ == "AGPL-3.0"


def test_list_components():
    """Test that list_components works."""
    components = osr.list_components()
    assert isinstance(components, list)
    assert len(components) > 0
    # Should contain core components
    expected_components = {'KillSwing', 'AssistSwing', 'DeathSwing', 'ObjectiveSwing', 'HoldSwing', 'APR', 'ADRa'}
    assert expected_components.issubset(set(components))


def test_core_functions_exist():
    """Test that core functions are available."""
    assert hasattr(osr, 'calculate_rating')
    assert hasattr(osr, 'calculate_rating_with_player_info')
    assert hasattr(osr, 'get_components')
    assert hasattr(osr, 'aggregate_ratings')
    assert hasattr(osr, 'load_match_data')
    assert hasattr(osr, 'load_config_data')


def test_component_management():
    """Test component registry functions."""
    assert hasattr(osr, 'add_component')
    assert hasattr(osr, 'remove_component')
    assert hasattr(osr, 'list_components')


@pytest.mark.parametrize('name', ['wp_model.json', 'rating_params.json', 'game_content.json'])
def test_data_files_ship_inside_the_package(name):
    """Calibration data must live inside the package so pip installs can find it."""
    assert (Path(osr.__file__).parent / 'data' / name).is_file()


def test_win_probability_model_is_sane():
    model = osr.WinProbabilityModel.load()

    def wp(atk, dfn, planted=False, time_left=1.0, per_player=3900):
        return model.attack_win_probability({
            'atk_alive': atk, 'def_alive': dfn, 'planted': planted, 'time_left': time_left,
            'atk_loadout': atk * per_player, 'def_loadout': dfn * per_player, 'map_id': None})

    assert 0.35 < wp(5, 5) < 0.65
    assert wp(5, 4) > wp(5, 5) > wp(4, 5)
    assert wp(2, 1) > 0.5
    # With no plant the attackers run out of time; after a plant the defenders do
    assert wp(2, 1, time_left=0.05) < wp(2, 1, time_left=0.8)
    assert wp(1, 2, planted=True, time_left=0.1) > wp(1, 2, planted=True, time_left=0.9)
