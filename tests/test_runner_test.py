"""Protect true-inference runs against import-time contract stubs."""
import sys
import types
import unittest
from unittest.mock import Mock, patch

from tests import run_tests


class TestRunnerIsolation(unittest.TestCase):
    def run_with(self, argv, enabled):
        utils = types.ModuleType('tests.utils')
        utils.add_extension_paths = Mock()
        utils.should_run_model_tests = lambda: enabled
        loader = Mock()
        loader.loadTestsFromName.side_effect = lambda name: unittest.TestSuite()
        runner = Mock()
        runner.run.return_value.wasSuccessful.return_value = True
        with patch.dict(sys.modules, {'tests.utils': utils}), \
                patch.object(sys, 'argv', argv), \
                patch.object(run_tests.unittest, 'TestLoader', return_value=loader), \
                patch.object(run_tests.unittest, 'TextTestRunner', return_value=runner), \
                patch.object(run_tests.subprocess, 'run') as child:
            child.return_value.returncode = 0
            success = run_tests.run_all_tests()
        return success, loader, child

    def test_selected_model_does_not_import_contract_tests(self):
        name = 'tests.model.sd_model_test.TestSD1Model'
        success, loader, child = self.run_with(['runner', '--test', name], True)
        self.assertTrue(success)
        loader.loadTestsFromName.assert_called_once_with(name)
        loader.discover.assert_not_called()
        child.assert_not_called()

    def test_short_test_names_remain_supported(self):
        success, loader, _ = self.run_with(["runner", "--test", "ss_executor_test"], False)
        self.assertTrue(success)
        loader.loadTestsFromName.assert_called_once_with("tests.ss_executor_test")

    def test_real_models_use_clean_interpreters(self):
        success, loader, child = self.run_with(['runner'], True)
        self.assertTrue(success)
        self.assertGreater(child.call_count, 0)
        for call in loader.loadTestsFromName.call_args_list:
            self.assertFalse(call.args[0].startswith('tests.model.'))
        for call in child.call_args_list:
            self.assertEqual(call.args[0][0], sys.executable)
            self.assertTrue(call.args[0][-1].startswith('tests.model.'))

    def test_default_does_not_launch_real_models(self):
        success, _, child = self.run_with(['runner'], False)
        self.assertTrue(success)
        child.assert_not_called()
