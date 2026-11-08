"""Resolve exact bundled packages without adding vendor roots to sys.path.

Only the application composition root installs this finder. Subprocess runtimes
do not install it and can use a separately installed newer DiffSynth.
"""
import importlib.abc
import importlib.util
from pathlib import Path
import sys


class BundledPackages(importlib.abc.MetaPathFinder):
    def __init__(self):
        root = Path(__file__).parent
        self.packages = {}
        for family in ("video", "voice", "mesh"):
            vendor = root / family / "vendor"
            for directory in sorted(vendor.iterdir()):
                if directory.is_dir() and (directory / "__init__.py").is_file():
                    self.packages[directory.name] = directory

    def find_spec(self, fullname, path=None, target=None):
        directory = self.packages.get(fullname)
        if directory is None:
            return None
        return importlib.util.spec_from_file_location(fullname, directory / "__init__.py",
            submodule_search_locations=[str(directory)])


def install_bundled_packages():
    if not any(isinstance(finder, BundledPackages) for finder in sys.meta_path):
        sys.meta_path.insert(0, BundledPackages())
