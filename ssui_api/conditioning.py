from contextlib import ExitStack
from backend.flux.extensions.regional_prompting_extension import RegionalPromptingExtension
from backend.flux.modules.conditioner import HFEncoder
from backend.flux.text_conditioning import FluxTextConditioning
from backend.model_manager.config import ModelFormat
from backend.patches.model_patch_raw import ModelPatchRaw
from backend.stable_diffusion.diffusion.conditioning_data import (
    BasicConditioningInfo,
    FLUXConditioningInfo,
    Range,
    SDXLConditioningInfo,
    TextConditioningData,
    TextConditioningRegions,
)

from backend.util.devices import TorchDevice
from transformers import CLIPTextModel, CLIPTextModelWithProjection, CLIPTokenizer, T5EncoderModel, T5Tokenizer, T5TokenizerFast
import torchvision

from typing import Any, Callable, Dict, Iterator, Literal, Optional, Tuple, Union, cast
import torch

from safetensors.torch import load_file as safetensors_load_file
from torch import load as torch_load
from compel import Compel, ReturnedEmbeddingsType


from backend.util.devices import TorchDevice
from backend.util.mask import to_standard_float_mask

from .model import ClipModel, T5EncoderModel as ModelT5Encoder


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


def run_clip_compel(
    clip_model: ClipModel,
    prompt: str,
    get_pooled: bool,
    zero_on_empty: bool,
) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
    text_encoder_info = clip_model.text_encoder
    tokenizer = clip_model.tokenizer
    # return zero on empty
    if prompt == "" and zero_on_empty:
        cpu_text_encoder = text_encoder_info.model
        assert isinstance(cpu_text_encoder, torch.nn.Module)
        c = torch.zeros(
            (
                1,
                cpu_text_encoder.config.max_position_embeddings,
                cpu_text_encoder.config.hidden_size,
            ),
            dtype=cpu_text_encoder.dtype,
        )
        if get_pooled:
            c_pooled = torch.zeros(
                (1, cpu_text_encoder.config.hidden_size),
                dtype=c.dtype,
            )
        else:
            c_pooled = None
        return c, c_pooled

    with (
        # apply all patches while the model is on the target device
        text_encoder_info.model_on_device() as (cached_weights, text_encoder),
    ):
        assert isinstance(text_encoder, (CLIPTextModel, CLIPTextModelWithProjection))
        assert isinstance(tokenizer.model, CLIPTokenizer)

        text_encoder = cast(CLIPTextModel, text_encoder)
        compel = Compel(
            tokenizer=tokenizer.model,
            text_encoder=text_encoder,
            dtype_for_device_getter=TorchDevice.choose_torch_dtype,
            truncate_long_prompts=False,  # TODO:
            returned_embeddings_type=ReturnedEmbeddingsType.PENULTIMATE_HIDDEN_STATES_NON_NORMALIZED,  # TODO: clip skip
            requires_pooled=get_pooled,
            device=TorchDevice.choose_torch_device(),
        )

        conjunction = Compel.parse_prompt_string(prompt)

        # TODO: ask for optimizations? to not run text_encoder twice
        c, _options = compel.build_conditioning_tensor_for_conjunction(conjunction)
        if get_pooled:
            c_pooled = compel.conditioning_provider.get_pooled_embeddings([prompt])
        else:
            c_pooled = None

    del tokenizer
    del text_encoder
    del text_encoder_info

    c = c.detach().to("cpu")
    if c_pooled is not None:
        c_pooled = c_pooled.detach().to("cpu")

    return c, c_pooled


def create_sdxl_conditioning(
    prompt: str,
    style: str,
    clip_model: ClipModel,
    refiner_clip_model: ClipModel,
    original_height: int,
    original_width: int,
    crop_top: int,
    crop_left: int,
    target_height: int,
    target_width: int,
):
    c1, c1_pooled = run_clip_compel(clip_model, prompt, False, zero_on_empty=True)
    if style.strip() == "":
        c2, c2_pooled = run_clip_compel(
            refiner_clip_model, prompt, True, zero_on_empty=True
        )
    else:
        c2, c2_pooled = run_clip_compel(
            refiner_clip_model, style, True, zero_on_empty=True
        )

    original_size = (original_height, original_width)
    crop_coords = (crop_top, crop_left)
    target_size = (target_height, target_width)

    add_time_ids = torch.tensor([original_size + crop_coords + target_size])

    # [1, 77, 768], [1, 154, 1280]
    if c1.shape[1] < c2.shape[1]:
        c1 = torch.cat(
            [
                c1,
                torch.zeros(
                    (c1.shape[0], c2.shape[1] - c1.shape[1], c1.shape[2]),
                    device=c1.device,
                    dtype=c1.dtype,
                ),
            ],
            dim=1,
        )

    elif c1.shape[1] > c2.shape[1]:
        c2 = torch.cat(
            [
                c2,
                torch.zeros(
                    (c2.shape[0], c1.shape[1] - c2.shape[1], c2.shape[2]),
                    device=c2.device,
                    dtype=c2.dtype,
                ),
            ],
            dim=1,
        )

    assert c2_pooled is not None
    return SDXLConditioningInfo(
        embeds=torch.cat([c1, c2], dim=-1),
        pooled_embeds=c2_pooled,
        add_time_ids=add_time_ids,
    )


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



def create_flux_conditioning(prompt: str, t5_encoder: ModelT5Encoder, clip_model: ClipModel):
    def _t5_encode(prompt: str) -> torch.Tensor:
        prompt = [prompt]

        t5_encoder_info = t5_encoder.text_encoder
        t5_encoder_config = t5_encoder_info.config
        assert t5_encoder_config is not None
        t5_tokenizer = t5_encoder.tokenizer.model

        with (
            t5_encoder_info.model_on_device() as (cached_weights, t5_text_encoder),
            ExitStack() as exit_stack,
        ):
            assert isinstance(t5_text_encoder, T5EncoderModel)
            assert isinstance(t5_tokenizer, (T5Tokenizer, T5TokenizerFast))

            # Determine if the model is quantized.
            # If the model is quantized, then we need to apply the LoRA weights as sidecar layers. This results in
            # slower inference than direct patching, but is agnostic to the quantization format.
            if t5_encoder_config.format in [ModelFormat.T5Encoder, ModelFormat.Diffusers]:
                model_is_quantized = False
            elif t5_encoder_config.format in [
                ModelFormat.BnbQuantizedLlmInt8b,
                ModelFormat.BnbQuantizednf4b,
                ModelFormat.GGUFQuantized,
            ]:
                model_is_quantized = True
            else:
                raise ValueError(f"Unsupported model format: {t5_encoder_config.format}")

            hf_t5_encoder = HFEncoder(t5_text_encoder, t5_tokenizer, False, t5_encoder.max_seq_length)
            prompt_embeds = hf_t5_encoder(prompt)

        assert isinstance(prompt_embeds, torch.Tensor)
        return prompt_embeds

    def _clip_encode(prompt: str) -> torch.Tensor:
        prompt = [prompt]

        clip_text_encoder_info = clip_model.text_encoder
        clip_text_encoder_config = clip_text_encoder_info.config
        assert clip_text_encoder_config is not None
        clip_tokenizer = clip_model.tokenizer.model

        with (
            clip_text_encoder_info.model_on_device() as (cached_weights, clip_text_encoder),
            ExitStack() as exit_stack,
        ):
            assert isinstance(clip_text_encoder, CLIPTextModel)
            assert isinstance(clip_tokenizer, CLIPTokenizer)

            clip_encoder = HFEncoder(clip_text_encoder, clip_tokenizer, True, 77)
            pooled_prompt_embeds = clip_encoder(prompt)

        assert isinstance(pooled_prompt_embeds, torch.Tensor)
        return pooled_prompt_embeds

    t5_embeddings = _t5_encode(prompt)
    clip_embeddings = _clip_encode(prompt)
    return FLUXConditioningInfo(clip_embeds=clip_embeddings, t5_embeds=t5_embeddings)

def _load_text_conditioning(
    cond_list: list[FLUXConditioningInfo],
    masks: Optional[list[Optional[torch.Tensor]]],
    packed_height: int,
    packed_width: int,
    dtype: torch.dtype,
    device: torch.device,
) -> list[FluxTextConditioning]:
    """Load text conditioning data from a FluxConditioningField or a list of FluxConditioningFields."""

    text_conditionings: list[FluxTextConditioning] = []
    for flux_conditioning_idx, flux_conditioning in enumerate(cond_list):
        # Load the text embeddings.
        flux_conditioning = flux_conditioning.to(dtype=dtype, device=device)
        t5_embeddings = flux_conditioning.t5_embeds
        clip_embeddings = flux_conditioning.clip_embeds

        # Load the mask, if provided.
        mask: Optional[torch.Tensor] = masks[flux_conditioning_idx] if masks is not None else None
        if mask is not None:
            mask = mask.to(device=device)
            mask = RegionalPromptingExtension.preprocess_regional_prompt_mask(
                mask, packed_height, packed_width, dtype, device
            )

        text_conditionings.append(FluxTextConditioning(t5_embeddings, clip_embeddings, mask))

    return text_conditionings