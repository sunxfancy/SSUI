class LatentFormat:
    scale_factor = 1.0
    latent_channels = 4
    latent_dimensions = 2
    latent_rgb_factors = None
    latent_rgb_factors_bias = None
    taesd_decoder_name = None

    def process_in(self, latent):
        return latent * self.scale_factor

    def process_out(self, latent):
        return latent / self.scale_factor