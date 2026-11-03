"""Portable inference-only INT8 Linear weights using ordinary PyTorch tensors.

Per-output-channel symmetric quantization. Storage and state_dicts contain INT8
weights and FP32 scales; floating weights exist only while computing a block.
No platform-specific quantized kernels or external quantization package is used.
"""
import math

import torch
from torch import nn
from torch.nn import functional as F


_BLOCK_ELEMENTS = 1 << 20
_CUSTOM_LINEAR_TYPES = {}


def _rows(in_features):
    return max(1, _BLOCK_ELEMENTS // max(1, in_features))


class _LowRankResidual(nn.Module):
    def __init__(self, up, down, alpha):
        super().__init__()
        self.register_buffer('up', up.detach().clone())
        self.register_buffer('down', down.detach().clone())
        self.register_buffer('alpha', torch.as_tensor(alpha, dtype=torch.float32, device=up.device).clone())

    def _apply(self, fn, recurse=True):
        alpha = self._buffers.pop('alpha')
        try:
            result = super()._apply(fn, recurse=recurse)
        finally:
            self._buffers['alpha'] = alpha.to(device=self.up.device, dtype=torch.float32)
        return result

    def forward(self, input, dtype):
        up = self.up.to(device=input.device, dtype=dtype)
        down = self.down.to(device=input.device, dtype=dtype)
        return F.linear(F.linear(input, down), up) * self.alpha.to(input.device)


class Int8Linear(nn.Linear):
    """Inference Linear with compressed weights; use quantize_model_int8().

    `weight` provides a temporary dense compatibility view for model code that
    accesses weights directly. Assignment/merging into that view is unsupported;
    LoRA must use sidecars. The normal forward dequantizes output-row blocks.
    """

    @property
    def weight(self):
        return self.dequantize_weight()

    def dequantize_weight(self, start=0, end=None, *, device=None, include_lora=True):
        device = self._int8_dtype.device if device is None else device
        packed = self._int8_weight[start:end].to(device=device).float()
        scale = self._int8_scale[start:end].to(device=device, dtype=torch.float32)
        weight = packed * scale
        if include_lora:
            for residual in self._int8_loras:
                up = residual.up[start:end].to(device=device, dtype=torch.float32)
                down = residual.down.to(device=device, dtype=torch.float32)
                weight = weight + (up @ down) * residual.alpha.to(device)
        limit = torch.finfo(self._int8_dtype.dtype).max
        return weight.clamp_(-limit, limit).to(dtype=self._int8_dtype.dtype)

    def _apply(self, fn, recurse=True):
        # .half()/.bfloat16() must not underflow the scale. Use the zero-sized
        # floating buffer to follow the requested compute dtype and device.
        scale = self._buffers.pop('_int8_scale')
        try:
            result = super()._apply(fn, recurse=recurse)
        finally:
            self._buffers['_int8_scale'] = scale.to(device=self._int8_dtype.device, dtype=torch.float32)
        return result

    def quantized_forward(self, input):
        bias = self.bias
        if bias is not None:
            bias = bias.to(device=input.device, dtype=self._int8_dtype.dtype)
        if self.out_features == 0:
            return F.linear(input, self.dequantize_weight(device=input.device), bias)
        outputs = []
        step = _rows(self.in_features)
        for start in range(0, self.out_features, step):
            end = min(start + step, self.out_features)
            weight = self.dequantize_weight(start, end, device=input.device, include_lora=False)
            outputs.append(F.linear(input, weight, None if bias is None else bias[start:end]))
        result = outputs[0] if len(outputs) == 1 else torch.cat(outputs, dim=-1)
        for residual in self._int8_loras:
            result = result + residual(input, self._int8_dtype.dtype)
        return result

    @torch.no_grad()
    def add_lora(self, up, down, alpha=1.):
        if up.ndim != 2 or down.ndim != 2 or up.shape[0] != self.out_features or down.shape[1] != self.in_features or up.shape[1] != down.shape[0]:
            raise ValueError('LoRA shape does not match the quantized Linear')
        if not math.isfinite(float(alpha)) or not torch.isfinite(up).all() or not torch.isfinite(down).all():
            raise ValueError('LoRA weights and scale must be finite')
        device, dtype = self._int8_dtype.device, self._int8_dtype.dtype
        self._int8_loras.append(_LowRankResidual(up.to(device=device, dtype=dtype), down.to(device=device, dtype=dtype), alpha))

    @torch.no_grad()
    def merge_weight_delta(self, delta):
        """Merge an already-dense native LoRA delta blockwise and requantize.

        Low-rank loaders should use add_lora() instead to avoid another rounding.
        Copy in place so shared packed buffers and cache snapshots stay coherent.
        """
        if tuple(delta.shape) != (self.out_features, self.in_features):
            raise ValueError('Weight delta shape does not match the quantized Linear')
        if not torch.isfinite(delta).all():
            raise ValueError('Weight delta must be finite')
        for start in range(0, self.out_features, _rows(self.in_features)):
            end = min(start + _rows(self.in_features), self.out_features)
            # Merge in FP32 even when the model's compute dtype is FP16/BF16.
            base = self._int8_weight[start:end].float() * self._int8_scale[start:end]
            merged = base + delta[start:end].to(device=base.device, dtype=torch.float32)
            limit = torch.finfo(self._int8_dtype.dtype).max
            if not torch.isfinite(merged).all() or (merged.abs() > limit).any():
                raise ValueError('Merged weight exceeds the model compute dtype range')
        for start in range(0, self.out_features, _rows(self.in_features)):
            end = min(start + _rows(self.in_features), self.out_features)
            base = self._int8_weight[start:end].float() * self._int8_scale[start:end]
            merged = base + delta[start:end].to(device=base.device, dtype=torch.float32)
            packed, scale = _pack(merged)
            self._int8_weight[start:end].copy_(packed)
            self._int8_scale[start:end].copy_(scale)

    def _load_from_state_dict(self, state_dict, prefix, local_metadata, strict,
                              missing_keys, unexpected_keys, error_msgs):
        # Reconstruct sidecar structure before the normal recursive buffer load.
        stem = prefix + '_int8_loras.'
        indices = {int(key[len(stem):].split('.')[0]) for key in state_dict
                   if key.startswith(stem) and key[len(stem):].split('.')[0].isdigit()}
        residuals = nn.ModuleList()
        for index in range(len(indices)):
            keys = [stem + str(index) + '.' + name for name in ('up', 'down', 'alpha')]
            if any(key not in state_dict for key in keys):
                error_msgs.append('Incomplete INT8 LoRA state at ' + stem + str(index))
                break
            up, down, alpha = [state_dict[key] for key in keys]
            if up.ndim != 2 or down.ndim != 2 or up.shape[0] != self.out_features or down.shape[1] != self.in_features or up.shape[1] != down.shape[0] or alpha.numel() != 1:
                error_msgs.append('Invalid INT8 LoRA shape at ' + stem + str(index))
                break
            device, dtype = self._int8_dtype.device, self._int8_dtype.dtype
            residuals.append(_LowRankResidual(torch.empty_like(up, device=device, dtype=dtype),
                                             torch.empty_like(down, device=device, dtype=dtype), 1.))
        self._int8_loras = residuals
        super()._load_from_state_dict(state_dict, prefix, local_metadata, strict,
                                     missing_keys, unexpected_keys, error_msgs)

    def forward(self, input):
        return self.quantized_forward(input)


def _pack(weight):
    packed = torch.empty(weight.shape, dtype=torch.int8, device=weight.device)
    scales = torch.empty((weight.shape[0], 1), dtype=torch.float32, device=weight.device)
    for start in range(0, weight.shape[0], _rows(weight.shape[1])):
        end = min(start + _rows(weight.shape[1]), weight.shape[0])
        block = weight[start:end].detach().float()
        if weight.shape[1] == 0:
            scales[start:end].fill_(1)
            continue
        maximum = block.abs().amax(dim=1, keepdim=True)
        scale = torch.where(maximum > 0, (maximum / 127).clamp_min(torch.finfo(torch.float32).tiny), 1.)
        packed[start:end] = (block / scale).round().clamp_(-127, 127).to(torch.int8)
        scales[start:end] = scale
    return packed, scales


@torch.no_grad()
def quantize_model_int8(model, *, exclude=(), linear_types=()):
    """Convert plain Linear layers in place, preserving aliases and hooks.

    Ties between Linear and unconverted layers (e.g. the vocabulary embedding)
    remain dense so tying semantics are preserved. Already quantized/custom
    Linear subclasses are not converted. `exclude` contains module-name prefixes.
    """
    if not isinstance(model, nn.Module):
        return model
    supported_types = {nn.Linear, *linear_types}
    excluded = set(exclude)
    candidates = []
    uses = {}
    # remove_duplicate=False also exposes aliases with excluded paths.
    blocked = set()
    for name, layer in model.named_modules(remove_duplicate=False):
        for parameter in layer.parameters(recurse=False):
            uses.setdefault(id(parameter), set()).add(id(layer))
        if any(name == prefix or name.startswith(prefix + '.') for prefix in excluded):
            blocked.add(id(layer))
    for layer in model.modules():
        if type(layer) in supported_types and id(layer) not in blocked and type(layer.weight) is nn.Parameter:
            candidates.append(layer)
    candidate_ids = {id(layer) for layer in candidates}
    candidates = [layer for layer in candidates if uses[id(layer.weight)] <= candidate_ids]
    # Validate before mutating anything. An invalid later layer must not leave
    # an otherwise usable model partially converted.
    for layer in candidates:
        if layer.weight.device.type == 'meta':
            raise ValueError('INT8 requires materialized weights, not meta tensors')
        if layer.weight.dtype not in (torch.float16, torch.bfloat16, torch.float32):
            raise ValueError('INT8 supports float16, bfloat16 and float32 Linear weights')
        for start in range(0, layer.out_features, _rows(layer.in_features)):
            if not torch.isfinite(layer.weight[start:start + _rows(layer.in_features)]).all():
                raise ValueError('Cannot quantize non-finite Linear weights')
    shared = {}
    for layer in candidates:
        weight = layer.weight
        key = id(weight)
        if key not in shared:
            shared[key] = _pack(weight)
        packed, scale = shared[key]
        marker = torch.empty(0, dtype=weight.dtype, device=weight.device)
        # Identity is retained for aliased modules and external references.
        del layer._parameters['weight']
        layer.register_buffer('_int8_weight', packed)
        layer.register_buffer('_int8_scale', scale)
        layer.register_buffer('_int8_dtype', marker)
        layer.add_module('_int8_loras', nn.ModuleList())
        layer.requires_grad_(False)
        original_type = type(layer)
        if original_type is nn.Linear:
            layer.__class__ = Int8Linear
        else:
            if original_type not in _CUSTOM_LINEAR_TYPES:
                _CUSTOM_LINEAR_TYPES[original_type] = type('Int8' + original_type.__name__,
                    (Int8Linear, original_type), {'forward': original_type.forward})
            layer.__class__ = _CUSTOM_LINEAR_TYPES[original_type]
    if any(isinstance(layer, Int8Linear) for layer in model.modules()):
        model._ssui_int8 = True
    return model


def quantized_weight_keys(model):
    """Logical weight names for native checkpoint/LoRA matching, without decoding."""
    return {name + '.weight' if name else 'weight' for name, layer in model.named_modules()
            if isinstance(layer, Int8Linear)}


def quantized_linear_for_weight(model, name):
    if name == 'weight':
        layer = model
    elif name.endswith('.weight'):
        try:
            layer = model.get_submodule(name[:-7])
        except AttributeError:
            return None
    else:
        return None
    return layer if isinstance(layer, Int8Linear) else None
