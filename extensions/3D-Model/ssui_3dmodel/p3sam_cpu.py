"""Compatibility for CPU spconv's unfused bias path; inference mathematics unchanged."""
def configure_cpu():
    import torch
    import spconv.pytorch as spconv

    torch.set_num_threads(8)
    original = spconv.SubMConv3d.forward

    def forward(module, tensor, *args, **kwargs):
        bias = module.bias
        if tensor.features.is_cuda or bias is None:
            return original(module, tensor, *args, **kwargs)
        # CPU spconv cannot fuse bias. Apply it separately after convolution.
        module.bias = None
        try:
            output = original(module, tensor, *args, **kwargs)
        finally:
            module.bias = bias
        return output.replace_feature(output.features + bias)

    spconv.SubMConv3d.forward = forward
