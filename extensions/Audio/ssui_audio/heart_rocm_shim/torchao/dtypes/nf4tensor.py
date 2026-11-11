"""Raise if the unsupported NF4 quantization path is actually selected."""


class NF4Tensor:
    pass


def to_nf4(*args, **kwargs):
    raise RuntimeError("NF4 quantization is unavailable on Windows ROCm")


def linear_nf4(*args, **kwargs):
    raise RuntimeError("NF4 quantization is unavailable on Windows ROCm")


def implements(_operations):
    def register(function):
        return function

    return register
