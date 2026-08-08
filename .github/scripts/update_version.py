# ruff: noqa: INP001
"""Update the integration version files for a release."""

import json
import os
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def update_version(tag: str) -> None:
    """Update the manifest and Python version constant.

    Args:
        tag: Release tag to write as the integration version.

    Raises:
        RuntimeError: If the version constant cannot be found.
    """
    manifest_path = PROJECT_ROOT / "custom_components/variable/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["version"] = tag
    manifest_path.write_text(json.dumps(manifest, indent=4) + "\n")

    const_path = PROJECT_ROOT / "custom_components/variable/const.py"
    const = const_path.read_text()
    const, replacements = re.subn(
        r'^VERSION = ".*"$',
        f'VERSION = "{tag}"',
        const,
        count=1,
        flags=re.MULTILINE,
    )
    if replacements != 1:
        raise RuntimeError("Unable to update VERSION in const.py")
    const_path.write_text(const)


def main() -> None:
    """Update version files from the release workflow environment."""
    update_version(os.environ["RELEASE_TAG"])


if __name__ == "__main__":
    main()
