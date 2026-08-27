import importlib
import unittest
from unittest.mock import patch

import torch


class DiffusersCompatibilityTest(unittest.TestCase):
    def test_torch_24_preload_disables_and_restores_custom_op_decorators(self):
        from ssui_image.diffusers_compat import preload_attention_dispatch_for_torch_24

        original_custom_op = torch.library.custom_op
        original_register_fake = torch.library.register_fake

        def load_attention_dispatch(_module_name):
            self.assertIsNot(torch.library.custom_op, original_custom_op)
            self.assertIsNot(torch.library.register_fake, original_register_fake)

            custom_decorator = torch.library.custom_op(
                "_diffusers_flash_attn_3::_flash_attn_forward", mutates_args=()
            )
            fake_decorator = torch.library.register_fake(
                "_diffusers_flash_attn_3::_flash_attn_forward"
            )
            function = lambda: None
            self.assertIs(custom_decorator(function), function)
            self.assertIs(fake_decorator(function), function)
            return object()

        with (
            patch.object(torch, "__version__", "2.4.1+cu124"),
            patch.object(importlib, "import_module", side_effect=load_attention_dispatch) as import_module,
        ):
            preload_attention_dispatch_for_torch_24()

        import_module.assert_called_once_with("diffusers.models.attention_dispatch")
        self.assertIs(torch.library.custom_op, original_custom_op)
        self.assertIs(torch.library.register_fake, original_register_fake)

    def test_other_torch_versions_do_not_preload(self):
        from ssui_image.diffusers_compat import preload_attention_dispatch_for_torch_24

        with (
            patch.object(torch, "__version__", "2.5.0"),
            patch.object(importlib, "import_module") as import_module,
        ):
            preload_attention_dispatch_for_torch_24()

        import_module.assert_not_called()


if __name__ == "__main__":
    unittest.main()
