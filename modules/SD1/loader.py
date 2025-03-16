import common.util as utils
import common.model_detection as model_detection
import common.model_management as model_management
import common.model_patcher as model_patcher
import logging
import torch


class CheckpointLoader:
    def __init__(self, sd, diffusion_model_prefix, parameters, weight_dtype, load_device, model_config):
        self.sd = sd
        self.diffusion_model_prefix = diffusion_model_prefix
        self.parameters = parameters
        self.weight_dtype = weight_dtype
        self.load_device = load_device
        self.model_config = model_config

    def load_vae(self) -> VAE:
        vae_sd = utils.state_dict_prefix_replace(self.sd, {k: "" for k in self.model_config.vae_key_prefix}, filter_keys=True)
        vae_sd = self.model_config.process_vae_state_dict(vae_sd)
        return VAE(sd=vae_sd)

    def load_clip(self, embedding_directory=None, te_model_options={}) -> CLIP:
        clip_target = self.model_config.clip_target(state_dict=self.sd)
        if clip_target is None:
            raise RuntimeError("ERROR: Could not get CLIP target in checkpoint")

        clip_sd = self.model_config.process_clip_state_dict(self.sd)
        if len(clip_sd) <= 0:
            logging.warning("no CLIP/text encoder weights in checkpoint, the text encoder model will not be loaded.")
            return None

        parameters = utils.calculate_parameters(clip_sd)
        clip = CLIP(clip_target, embedding_directory=embedding_directory, tokenizer_data=clip_sd, parameters=parameters, model_options=te_model_options)
        m, u = clip.load_sd(clip_sd, full_model=True)
        if len(m) > 0:
            m_filter = list(filter(lambda a: ".logit_scale" not in a and ".transformer.text_projection.weight" not in a, m))
            if len(m_filter) > 0:
                logging.warning("clip missing: {}".format(m))
            else:
                logging.debug("clip missing: {}".format(m))

        if len(u) > 0:
            logging.debug("clip unexpected {}:".format(u))
            
        return clip


    def load_unet(self):
        inital_load_device = model_management.unet_inital_load_device(self.parameters, self.unet_dtype)
        model = self.model_config.get_model(self.sd, self.diffusion_model_prefix, device=inital_load_device)
        model.load_model_weights(self.sd, self.diffusion_model_prefix)

        patcher = model_patcher.ModelPatcher(model, load_device=self.load_device, offload_device=model_management.unet_offload_device())
        if self.inital_load_device != torch.device("cpu"):
            logging.info("loaded diffusion model directly to GPU")
            model_management.load_models_gpu([patcher], force_full_load=True)
        
        return patcher


    @classmethod
    def load(ckpt_path: str, model_options={}) -> "CheckpointLoader":
        sd = utils.load_torch_file(ckpt_path)
        diffusion_model_prefix = model_detection.unet_prefix_from_state_dict(sd)
        parameters = utils.calculate_parameters(sd, diffusion_model_prefix)
        weight_dtype = utils.weight_dtype(sd, diffusion_model_prefix)
        load_device = model_management.get_torch_device()
        model_config = model_detection.model_config_from_unet(sd, diffusion_model_prefix)
        if model_config is None:
            raise RuntimeError("ERROR: Could not detect model type of: {}".format(ckpt_path))
        
        unet_weight_dtype = list(model_config.supported_inference_dtypes)
        if weight_dtype is not None and model_config.scaled_fp8 is None:
            unet_weight_dtype.append(weight_dtype)

        model_config.custom_operations = model_options.get("custom_operations", None)
        unet_dtype = model_options.get("dtype", model_options.get("weight_dtype", None))
        if unet_dtype is None:
            unet_dtype = model_management.unet_dtype(model_params=parameters, supported_dtypes=unet_weight_dtype)

        manual_cast_dtype = model_management.unet_manual_cast(unet_dtype, load_device, model_config.supported_inference_dtypes)
        model_config.set_inference_dtype(unet_dtype, manual_cast_dtype)
        return CheckpointLoader(sd, diffusion_model_prefix, parameters, weight_dtype, load_device, model_config)


