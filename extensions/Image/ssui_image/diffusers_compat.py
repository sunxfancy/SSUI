"""Compatibility helpers for supported Diffusers/PyTorch combinations."""

import importlib

import torch


def preload_attention_dispatch_for_torch_24() -> None:
    """Load Diffusers attention dispatch without unsupported Torch 2.4 custom ops.

    Diffusers 0.37+ registers Flash Attention 3 wrappers using annotations
    postponed by ``from __future__ import annotations``. Torch 2.4's schema
    inference cannot resolve those string annotations, so importing any model
    that reaches attention_dispatch fails. These wrappers require newer Torch
    features and are not usable on 2.4, so load the module with their decorators
    disabled while leaving the rest of torch.library untouched at runtime.
    """

    version_parts = torch.__version__.split("+", 1)[0].split(".")
    if tuple(int(part) for part in version_parts[:2]) != (2, 4):
        return

    original_custom_op = torch.library.custom_op
    original_register_fake = torch.library.register_fake

    def passthrough_decorator(*_args, **_kwargs):
        def decorate(function):
            return function

        return decorate

    def compatible_custom_op(name, *args, **kwargs):
        if name.startswith("_diffusers_flash_attn_3::"):
            return passthrough_decorator(name, *args, **kwargs)
        return original_custom_op(name, *args, **kwargs)

    def compatible_register_fake(op, *args, **kwargs):
        if isinstance(op, str) and op.startswith("_diffusers_flash_attn_3::"):
            return passthrough_decorator(op, *args, **kwargs)
        return original_register_fake(op, *args, **kwargs)

    torch.library.custom_op = compatible_custom_op
    torch.library.register_fake = compatible_register_fake
    try:
        importlib.import_module("diffusers.models.attention_dispatch")
    finally:
        torch.library.custom_op = original_custom_op
        torch.library.register_fake = original_register_fake
