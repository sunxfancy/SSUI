import argparse
from pathlib import Path
import subprocess
import sys
import unittest


def run_all_tests():
    """Run contracts and real inference in separate processes.

    Contract tests install fake third-party modules at import time. Importing
    them before real-model discovery can turn a GPU regression into a fake pass.
    Selected tests must also be loaded without discovering unrelated modules.
    """
    tests_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(tests_dir.parent))
    from tests.utils import add_extension_paths, should_run_model_tests
    add_extension_paths()

    parser = argparse.ArgumentParser(description='运行测试')
    parser.add_argument('--test', type=str, help='指定要运行的单个测试名称')
    args = parser.parse_args()
    loader = unittest.TestLoader()
    runner = unittest.TextTestRunner(verbosity=2)
    if args.test:
        name = args.test if args.test.startswith("tests.") else f"tests.{args.test}"
        return runner.run(loader.loadTestsFromName(name)).wasSuccessful()

    # Do not recurse into model/: each test module gets a clean interpreter below.
    suite = unittest.TestSuite(
        loader.loadTestsFromName(f'tests.{path.stem}')
        for path in sorted(tests_dir.glob('*_test.py'))
    )
    success = runner.run(suite).wasSuccessful()
    if should_run_model_tests():
        for path in sorted((tests_dir / 'model').glob('*_test.py')):
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), '--test',
                 f'tests.model.{path.stem}'],
                cwd=tests_dir.parent,
            )
            success = result.returncode == 0 and success
    return success


if __name__ == '__main__':
    sys.exit(0 if run_all_tests() else 1)
