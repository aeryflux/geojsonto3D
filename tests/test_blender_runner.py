"""
Unit tests for blender_runner module
"""

import unittest
import json
import sys
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
import tempfile
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from blender_runner import (
    load_cache,
    save_cache,
    verify_blender,
    build_script_args,
    PRESETS
)


class TestCacheOperations(unittest.TestCase):
    """Test cache loading and saving operations"""

    def test_load_cache_nonexistent(self):
        """Test loading cache when file doesn't exist"""
        with patch('pathlib.Path.exists', return_value=False):
            result = load_cache('.nonexistent.json')
            self.assertEqual(result, {})

    def test_load_cache_valid(self):
        """Test loading valid cache file"""
        test_data = {"blender_path": "/usr/bin/blender"}
        mock_file = mock_open(read_data=json.dumps(test_data))

        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_file):
                result = load_cache('.test_cache.json')
                self.assertEqual(result, test_data)

    def test_load_cache_invalid_json(self):
        """Test loading cache with invalid JSON"""
        mock_file = mock_open(read_data="invalid json{")

        with patch('pathlib.Path.exists', return_return_value=True):
            with patch('builtins.open', mock_file):
                result = load_cache('.test_cache.json')
                self.assertEqual(result, {})

    def test_save_cache_success(self):
        """Test successful cache saving"""
        test_data = {"blender_path": "/usr/bin/blender"}
        mock_file = mock_open()

        with patch('builtins.open', mock_file):
            result = save_cache('.test_cache.json', test_data)
            self.assertTrue(result)
            mock_file.assert_called_once()

    def test_save_cache_failure(self):
        """Test cache saving failure"""
        test_data = {"blender_path": "/usr/bin/blender"}

        with patch('builtins.open', side_effect=IOError("Permission denied")):
            result = save_cache('.test_cache.json', test_data)
            self.assertFalse(result)


class TestBlenderVerification(unittest.TestCase):
    """Test Blender executable verification"""

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_verify_blender_success(self, mock_exists, mock_run):
        """Test successful Blender verification"""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        result = verify_blender('/usr/bin/blender')
        self.assertTrue(result)

    @patch('pathlib.Path.exists')
    def test_verify_blender_not_found(self, mock_exists):
        """Test Blender verification when file doesn't exist"""
        mock_exists.return_value = False

        result = verify_blender('/nonexistent/blender')
        self.assertFalse(result)

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_verify_blender_execution_failure(self, mock_exists, mock_run):
        """Test Blender verification when execution fails"""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=1)

        result = verify_blender('/usr/bin/blender')
        self.assertFalse(result)

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_verify_blender_timeout(self, mock_exists, mock_run):
        """Test Blender verification timeout"""
        mock_exists.return_value = True
        mock_run.side_effect = Exception("Timeout")

        result = verify_blender('/usr/bin/blender')
        self.assertFalse(result)


class TestPresets(unittest.TestCase):
    """Test preset configurations"""

    def test_presets_exist(self):
        """Test that all required presets exist"""
        required_presets = ['low', 'medium', 'high', 'ultra']
        for preset in required_presets:
            self.assertIn(preset, PRESETS)

    def test_preset_structure(self):
        """Test that presets have required keys"""
        required_keys = ['ico_subdiv', 'extrude_above', 'extrude_below',
                        'border_width', 'border_height', 'enable_borders', 'enable_cities']

        for preset_name, preset in PRESETS.items():
            for key in required_keys:
                self.assertIn(key, preset, f"Preset '{preset_name}' missing key '{key}'")

    def test_preset_values_valid(self):
        """Test that preset values are within valid ranges"""
        for preset_name, preset in PRESETS.items():
            # ICO_SUBDIV should be between 1 and 7
            self.assertGreaterEqual(preset['ico_subdiv'], 1)
            self.assertLessEqual(preset['ico_subdiv'], 7)

            # Extrusion values should be non-negative
            self.assertGreaterEqual(preset['extrude_above'], 0)
            self.assertGreaterEqual(preset['extrude_below'], 0)

            # Border dimensions should be positive
            self.assertGreater(preset['border_width'], 0)
            self.assertGreater(preset['border_height'], 0)

            # Boolean flags
            self.assertIsInstance(preset['enable_borders'], bool)
            self.assertIsInstance(preset['enable_cities'], bool)


class TestScriptArgs(unittest.TestCase):
    """Test script argument building"""

    def test_build_script_args_basic(self):
        """Test basic script argument building"""
        config = {
            'ico_subdiv': 5,
            'extrude_above': 0.05,
            'extrude_below': 0.05,
            'enable_borders': True,
            'border_width': 0.0005,
            'border_height': 0.0025,
            'enable_cities': False
        }

        args = build_script_args(config)

        self.assertIn('--ico-subdiv', args)
        self.assertIn('5', args)
        self.assertIn('--extrude-above', args)
        self.assertIn('0.05', args)
        self.assertIn('--enable-border', args)
        self.assertIn('--disable-cities', args)

    def test_build_script_args_borders_disabled(self):
        """Test script args when borders are disabled"""
        config = {
            'ico_subdiv': 3,
            'extrude_above': 0.03,
            'extrude_below': 0.03,
            'enable_borders': False,
            'enable_cities': False
        }

        args = build_script_args(config)

        self.assertIn('--disable-border', args)
        self.assertNotIn('--border-width', args)
        self.assertNotIn('--border-height', args)

    def test_build_script_args_cities_enabled(self):
        """Test script args when cities are enabled"""
        config = {
            'ico_subdiv': 6,
            'extrude_above': 0.05,
            'extrude_below': 0.05,
            'enable_borders': True,
            'border_width': 0.0005,
            'border_height': 0.0025,
            'enable_cities': True
        }

        args = build_script_args(config)

        self.assertIn('--enable-cities', args)
        self.assertNotIn('--disable-cities', args)


class TestPresetOrder(unittest.TestCase):
    """Test preset quality ordering"""

    def test_preset_subdivision_order(self):
        """Test that presets are ordered by quality (ICO_SUBDIV)"""
        subdivisions = [PRESETS[p]['ico_subdiv'] for p in ['low', 'medium', 'high', 'ultra']]
        self.assertEqual(subdivisions, sorted(subdivisions))


if __name__ == '__main__':
    unittest.main()
