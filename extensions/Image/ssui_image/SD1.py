"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Select, Switch, Slider
_delegate = initialize_adapter(globals(), "image.SD1")
SD1Clip = param("ignoreLastLayer", Switch(), default=False)(_delegate("SD1Clip"))
class SD1Latent(SD1Latent):
    pass
SD1Latent = param(
    "width",
    Slider(512, 4096, 64, labels=[512, 768, 1024, 1536, 1920, 2048, 3840, 4096]),
    default=512,
)(param(
    "height",
    Slider(512, 4096, 64, labels=[512, 768, 1024, 1536, 1920, 2048, 3840, 4096]),
    default=512,
)(SD1Latent))
SD1Denoise = param(
    "steps",
    Slider(1, 100, 1, labels=[1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]),
    default=30,
)(param(
    "scheduler",
    Select(
        "ddim",
        "ddpm",
        "deis",
        "deis_k",
        "lms",
        "lms_k",
        "pndm",
        "heun",
        "heun_k",
        "euler",
        "euler_k",
        "euler_a",
        "kdpm_2",
        "kdpm_2_k",
        "kdpm_2_a",
        "kdpm_2_a_k",
        "dpmpp_2s",
        "dpmpp_2s_k",
        "dpmpp_2m",
        "dpmpp_2m_k",
        "dpmpp_2m_sde",
        "dpmpp_2m_sde_k",
        "dpmpp_3m",
        "dpmpp_3m_k",
        "dpmpp_sde",
        "dpmpp_sde_k",
        "unipc",
        "unipc_k",
        "lcm",
        "tcd",
    ),
    default="ddim",
)(param("CFG", Slider(0, 15, 0.1), default=7.5)(param("seed", Random(), default=123454321)(_delegate("SD1Denoise")))))
