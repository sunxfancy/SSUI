
from backend.stable_diffusion.diffusion.conditioning_data import (
    BasicConditioningInfo,
    Range,
    SDXLConditioningInfo,
    TextConditioningData,
    TextConditioningRegions,
)

from backend.util.devices import TorchDevice
from transformers import CLIPTextModel,  CLIPTokenizer
import torchvision

from typing import Any, Callable, Dict, Optional, Tuple, Union
import torch

from safetensors.torch import load_file as safetensors_load_file
from torch import load as torch_load
from compel import Compel


from backend.util.devices import TorchDevice
from backend.util.mask import to_standard_float_mask

from .model import ClipModel

def create_conditioning(prompt: str, clip_model: ClipModel):
    text_encoder = clip_model.text_encoder
    tokenizer = clip_model.tokenizer
    
    with (text_encoder.model_on_device() as (cached_weights, text_encoder),):
        tokenizer = tokenizer.model
        print("text_encoder: ", text_encoder)
        print("tokenizer: ", tokenizer)
        assert isinstance(text_encoder, CLIPTextModel)
        assert isinstance(tokenizer, CLIPTokenizer)

        compel = Compel(
            tokenizer=tokenizer,
            text_encoder=text_encoder,
            dtype_for_device_getter=TorchDevice.choose_torch_dtype,
            truncate_long_prompts=False,
            device=TorchDevice.choose_torch_device(),
        )

        conjunction = Compel.parse_prompt_string(prompt)
        c, _options = compel.build_conditioning_tensor_for_conjunction(conjunction)
        c = c.detach().to("cpu")
        return BasicConditioningInfo(embeds=c)
    

def get_conditioning_data(
    positive_conditioning_field: Union[
        BasicConditioningInfo, list[BasicConditioningInfo]
    ],
    negative_conditioning_field: Union[
        BasicConditioningInfo, list[BasicConditioningInfo]
    ],
    latent_height: int,
    latent_width: int,
    device: torch.device,
    dtype: torch.dtype,
    cfg_scale: float | list[float],
    steps: int,
    cfg_rescale_multiplier: float,
) -> TextConditioningData:

    def _get_text_embeddings_and_masks(
        cond_list: list[BasicConditioningInfo],
        device: torch.device,
        dtype: torch.dtype,
    ) -> tuple[
        Union[list[BasicConditioningInfo], list[SDXLConditioningInfo]],
        list[Optional[torch.Tensor]],
    ]:
        """Get the text embeddings and masks from the input conditioning fields."""
        text_embeddings: Union[
            list[BasicConditioningInfo], list[SDXLConditioningInfo]
        ] = []
        text_embeddings_masks: list[Optional[torch.Tensor]] = []
        for cond in cond_list:
            text_embeddings.append(cond.to(device=device, dtype=dtype))
            text_embeddings_masks.append(None)

        return text_embeddings, text_embeddings_masks

    def _preprocess_regional_prompt_mask(
        mask: Optional[torch.Tensor],
        target_height: int,
        target_width: int,
        dtype: torch.dtype,
    ) -> torch.Tensor:
        """Preprocess a regional prompt mask to match the target height and width.
        If mask is None, returns a mask of all ones with the target height and width.
        If mask is not None, resizes the mask to the target height and width using 'nearest' interpolation.

        Returns:
            torch.Tensor: The processed mask. shape: (1, 1, target_height, target_width).
        """

        if mask is None:
            return torch.ones((1, 1, target_height, target_width), dtype=dtype)

        mask = to_standard_float_mask(mask, out_dtype=dtype)

        tf = torchvision.transforms.Resize(
            (target_height, target_width),
            interpolation=torchvision.transforms.InterpolationMode.NEAREST,
        )

        # Add a batch dimension to the mask, because torchvision expects shape (batch, channels, h, w).
        mask = mask.unsqueeze(0)  # Shape: (1, h, w) -> (1, 1, h, w)
        resized_mask = tf(mask)
        return resized_mask

    def _concat_regional_text_embeddings(
        text_conditionings: Union[
            list[BasicConditioningInfo], list[SDXLConditioningInfo]
        ],
        masks: Optional[list[Optional[torch.Tensor]]],
        latent_height: int,
        latent_width: int,
        dtype: torch.dtype,
    ) -> tuple[
        Union[BasicConditioningInfo, SDXLConditioningInfo],
        Optional[TextConditioningRegions],
    ]:
        """Concatenate regional text embeddings into a single embedding and track the region masks accordingly."""
        if masks is None:
            masks = [None] * len(text_conditionings)
        assert len(text_conditionings) == len(masks)

        is_sdxl = type(text_conditionings[0]) is SDXLConditioningInfo

        all_masks_are_none = all(mask is None for mask in masks)

        text_embedding = []
        pooled_embedding = None
        add_time_ids = None
        cur_text_embedding_len = 0
        processed_masks = []
        embedding_ranges = []

        for prompt_idx, text_embedding_info in enumerate(text_conditionings):
            mask = masks[prompt_idx]

            if is_sdxl:
                # We choose a random SDXLConditioningInfo's pooled_embeds and add_time_ids here, with a preference for
                # prompts without a mask. We prefer prompts without a mask, because they are more likely to contain
                # global prompt information.  In an ideal case, there should be exactly one global prompt without a
                # mask, but we don't enforce this.

                # HACK(ryand): The fact that we have to choose a single pooled_embedding and add_time_ids here is a
                # fundamental interface issue. The SDXL Compel nodes are not designed to be used in the way that we use
                # them for regional prompting. Ideally, the DenoiseLatents invocation should accept a single
                # pooled_embeds tensor and a list of standard text embeds with region masks. This change would be a
                # pretty major breaking change to a popular node, so for now we use this hack.
                if pooled_embedding is None or mask is None:
                    pooled_embedding = text_embedding_info.pooled_embeds
                if add_time_ids is None or mask is None:
                    add_time_ids = text_embedding_info.add_time_ids

            text_embedding.append(text_embedding_info.embeds)
            if not all_masks_are_none:
                embedding_ranges.append(
                    Range(
                        start=cur_text_embedding_len,
                        end=cur_text_embedding_len
                        + text_embedding_info.embeds.shape[1],
                    )
                )
                processed_masks.append(
                    _preprocess_regional_prompt_mask(
                        mask, latent_height, latent_width, dtype=dtype
                    )
                )

            cur_text_embedding_len += text_embedding_info.embeds.shape[1]

        text_embedding = torch.cat(text_embedding, dim=1)
        assert len(text_embedding.shape) == 3  # batch_size, seq_len, token_len

        regions = None
        if not all_masks_are_none:
            regions = TextConditioningRegions(
                masks=torch.cat(processed_masks, dim=1),
                ranges=embedding_ranges,
            )

        if is_sdxl:
            return (
                SDXLConditioningInfo(
                    embeds=text_embedding,
                    pooled_embeds=pooled_embedding,
                    add_time_ids=add_time_ids,
                ),
                regions,
            )
        return BasicConditioningInfo(embeds=text_embedding), regions

    # Main workflow starts here
    # Normalize positive_conditioning_field and negative_conditioning_field to lists.
    cond_list = positive_conditioning_field
    if not isinstance(cond_list, list):
        cond_list = [cond_list]
    uncond_list = negative_conditioning_field
    if not isinstance(uncond_list, list):
        uncond_list = [uncond_list]

    cond_text_embeddings, cond_text_embedding_masks = _get_text_embeddings_and_masks(
        cond_list, device, dtype
    )
    uncond_text_embeddings, uncond_text_embedding_masks = (
        _get_text_embeddings_and_masks(uncond_list, device, dtype)
    )

    cond_text_embedding, cond_regions = _concat_regional_text_embeddings(
        text_conditionings=cond_text_embeddings,
        masks=cond_text_embedding_masks,
        latent_height=latent_height,
        latent_width=latent_width,
        dtype=dtype,
    )
    uncond_text_embedding, uncond_regions = _concat_regional_text_embeddings(
        text_conditionings=uncond_text_embeddings,
        masks=uncond_text_embedding_masks,
        latent_height=latent_height,
        latent_width=latent_width,
        dtype=dtype,
    )

    if isinstance(cfg_scale, list):
        assert (
            len(cfg_scale) == steps
        ), "cfg_scale (list) must have the same length as the number of steps"

    conditioning_data = TextConditioningData(
        uncond_text=uncond_text_embedding,
        cond_text=cond_text_embedding,
        uncond_regions=uncond_regions,
        cond_regions=cond_regions,
        guidance_scale=cfg_scale,
        guidance_rescale_multiplier=cfg_rescale_multiplier,
    )
    return conditioning_data