import torch

class SD1VAE:
    def __init__(self, sd=None, device=None, config=None, dtype=None):
        self.memory_used_encode = lambda shape, dtype: (1767 * shape[2] * shape[3]) * model_management.dtype_size(dtype) #These are for AutoencoderKL and need tweaking (should be lower)
        self.memory_used_decode = lambda shape, dtype: (2178 * shape[2] * shape[3] * 64) * model_management.dtype_size(dtype)
        self.downscale_ratio = 8
        self.upscale_ratio = 8
        self.latent_channels = 4
        self.latent_dim = 2
        self.output_channels = 3
        self.process_input = lambda image: image * 2.0 - 1.0
        self.process_output = lambda image: torch.clamp((image + 1.0) / 2.0, min=0.0, max=1.0)
        self.working_dtypes = [torch.bfloat16, torch.float32]

        self.downscale_index_formula = None
        self.upscale_index_formula = None

        if config is None:
            #default SD1.x/SD2.x VAE parameters
            ddconfig = {'double_z': True, 'z_channels': 4, 'resolution': 256, 'in_channels': 3, 'out_ch': 3, 'ch': 128, 'ch_mult': [1, 2, 4, 4], 'num_res_blocks': 2, 'attn_resolutions': [], 'dropout': 0.0}

            if 'encoder.down.2.downsample.conv.weight' not in sd and 'decoder.up.3.upsample.conv.weight' not in sd: #Stable diffusion x4 upscaler VAE
                ddconfig['ch_mult'] = [1, 2, 4]
                self.downscale_ratio = 4
                self.upscale_ratio = 4

            self.latent_channels = ddconfig['z_channels'] = sd["decoder.conv_in.weight"].shape[1]
            if 'post_quant_conv.weight' in sd:
                self.first_stage_model = AutoencoderKL(ddconfig=ddconfig, embed_dim=sd['post_quant_conv.weight'].shape[1])
            else:
                self.first_stage_model = AutoencodingEngine(regularizer_config={'target': "comfy.ldm.models.autoencoder.DiagonalGaussianRegularizer"},
                                                            encoder_config={'target': "comfy.ldm.modules.diffusionmodules.model.Encoder", 'params': ddconfig},
                                                            decoder_config={'target': "comfy.ldm.modules.diffusionmodules.model.Decoder", 'params': ddconfig})