# SPDX-FileCopyrightText: Copyright (c) 2021-2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.
#
# Modified by Jiale Xu
# The modifications are subject to the same license as the original.
#
# Modified by Yuze He
# The modifications are subject to the same license as the original.


"""
The ray marcher takes the raw output of the implicit representation and uses the volume rendering equation to produce composited colors and depths.
Based off of the implementation in MipNeRF (this one doesn't do any cone tracing though!)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class MipRayMarcher2(nn.Module):
    def __init__(self, activation_factory):
        super().__init__()
        self.activation_factory = activation_factory

    def run_forward(self, colors, densities, depths, semantics, rendering_options, normals=None):
        dtype = colors.dtype
        deltas = depths[:, :, 1:] - depths[:, :, :-1]
        colors_mid = (colors[:, :, :-1] + colors[:, :, 1:]) / 2
        densities_mid = (densities[:, :, :-1] + densities[:, :, 1:]) / 2
        depths_mid = (depths[:, :, :-1] + depths[:, :, 1:]) / 2
        semantics_mid = (semantics[:, :, :-1] + semantics[:, :, 1:]) / 2

        # using factory mode for better usability
        densities_mid = self.activation_factory(rendering_options)(densities_mid).to(dtype)

        density_delta = densities_mid * deltas

        alpha = 1 - torch.exp(-density_delta).to(dtype)

        for bid in range(len(rendering_options['levels'])):
            if rendering_options['levels'][bid] == 0:
                pass
            elif rendering_options['levels'][bid] == 1:
                alpha[bid] = alpha[bid] * (1 - semantics_mid[bid, ..., 0:1])
                semantics_mid[bid, ..., 0:1] = 0  # remove hair
                semantics_mid[bid, ..., 1:] = (semantics_mid[bid, ..., 1:] + 1e-6) / (torch.sum(semantics_mid[bid, ..., 1:], dim=-1, keepdim=True) + 1e-6)
            elif rendering_options['levels'][bid] == 2:
                alpha[bid] = alpha[bid] * (1 - semantics_mid[bid, ..., 0:1] - semantics_mid[bid, ..., 3:4])
                semantics_mid[bid, ..., 0:1] = 0  # remove hair
                semantics_mid[bid, ..., 3:4] = 0  # remove cloth
                semantics_mid[bid, ..., 1:3] = (semantics_mid[bid, ..., 1:3] + 1e-6) / (torch.sum(semantics_mid[bid, ..., 1:3], dim=-1, keepdim=True) + 1e-6)
            else:
                raise NotImplementedError("Only 0, 1, 2 levels are supported")

        alpha_shifted = torch.cat([torch.ones_like(alpha[:, :, :1]), 1-alpha + 1e-10], -2)
        weights = alpha * torch.cumprod(alpha_shifted, -2)[:, :, :-1]
        weights = weights.to(dtype)

        composite_rgb = torch.sum(weights * colors_mid, -2)
        weight_total = weights.sum(2)
        # composite_depth = torch.sum(weights * depths_mid, -2) / weight_total
        composite_depth = torch.sum(weights * depths_mid, -2)
        composite_semantics = torch.sum(weights * semantics_mid, -2)

        # clip the composite to min/max range of depths
        composite_depth = torch.nan_to_num(composite_depth, float('inf')).to(dtype)
        composite_depth = torch.clamp(composite_depth, torch.min(depths), torch.max(depths))

        if rendering_options.get('white_back', False):
            composite_rgb = composite_rgb + 1 - weight_total

        # rendered value scale is 0-1, comment out original mipnerf scaling
        # composite_rgb = composite_rgb * 2 - 1 # Scale to (-1, 1)

        return composite_rgb, composite_depth, composite_semantics, weights


    def forward(self, colors, densities, depths, semantics, rendering_options, normals=None):
        if normals is not None:
            raise NotImplementedError("Normals are not supported in the ray marcher yet.")
            composite_rgb, composite_depth, composite_normals, weights = self.run_forward(colors, densities, depths, rendering_options, normals)
            return composite_rgb, composite_depth, composite_normals, weights

        composite_rgb, composite_depth, composite_semantic, weights = self.run_forward(colors, densities, depths, semantics, rendering_options)
        return composite_rgb, composite_depth, composite_semantic, weights
