"""Regression tests for Home Assistant device tracker deprecations."""

import ast
from pathlib import Path
import unittest


DEVICE_TRACKER_PATH = (
    Path(__file__).parents[1] / "custom_components" / "variable" / "device_tracker.py"
)


class DeviceTrackerDeprecationTests(unittest.TestCase):
    """Verify the integration avoids deprecated device tracker APIs."""

    @classmethod
    def setUpClass(cls) -> None:
        """Parse the device tracker platform once for all tests."""
        cls.source = DEVICE_TRACKER_PATH.read_text(encoding="utf-8")
        cls.module = ast.parse(cls.source)
        cls.variable_class = next(
            node
            for node in cls.module.body
            if isinstance(node, ast.ClassDef) and node.name == "Variable"
        )

    def test_tracker_entity_is_imported_from_public_module(self) -> None:
        """TrackerEntity should use Home Assistant's public import path."""
        tracker_imports = [
            node.module
            for node in self.module.body
            if isinstance(node, ast.ImportFrom)
            and any(alias.name == "TrackerEntity" for alias in node.names)
        ]

        self.assertEqual(
            tracker_imports, ["homeassistant.components.device_tracker"]
        )

    def test_variable_does_not_override_location_name(self) -> None:
        """Variable should let TrackerEntity calculate location state."""
        method_names = {
            node.name
            for node in self.variable_class.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        self.assertNotIn("location_name", method_names)

    def test_deprecated_location_name_attribute_is_not_set(self) -> None:
        """Variable should not set TrackerEntity's deprecated shorthand."""
        attribute_names = {
            node.attr
            for node in ast.walk(self.variable_class)
            if isinstance(node, ast.Attribute)
        }

        self.assertNotIn("_attr_location_name", attribute_names)


if __name__ == "__main__":
    unittest.main()
