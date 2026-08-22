from ssui import workflow, Prompt, Image, Video
from ssui.config import SSUIConfig
from ssui_video.Wan2 import Wan2T2VModel, Wan2TextToVideo, Wan2I2VModel, Wan2ImageToVideo
from ssui_video.Wan22 import (
    Wan22TI2VModel,
    Wan22TextToVideo,
    Wan22ImageToVideo,
    Wan22T2VA14BModel,
    Wan22T2VA14BTextToVideo,
    Wan22I2VA14BModel,
    Wan22I2VA14BImageToVideo,
)
from ssui_video.LTX2 import LTX2TextToVideo, LTX2ImageToVideo
from ssui_video.MiniMaxH3 import H3TextToVideo, H3ImageToVideo
from ssui_video.Hunyuan import HunyuanImageToVideoModel, HunyuanImageToVideo
from ssui_video.CogVideo import CogVideoModel, CogVideoTextToVideo

config = SSUIConfig()


@workflow
def txt2vid_wan2(prompt: Prompt, negative_prompt: Prompt) -> Video:
    """Wan 2.1-14B 文生视频（本地，推荐 24GB+ 显存）。"""
    if config.is_prepare():
        model = Wan2T2VModel()
    else:
        model = Wan2T2VModel.load()
    video = Wan2TextToVideo(config("Generate Video"), model, prompt, negative_prompt)
    return Video("mp4", video, fps=16)


@workflow
def img2vid_wan2(image: Image, prompt: Prompt, negative_prompt: Prompt, end_image: Image = None) -> Video:
    """Wan 2.1-I2V-14B-720P 图生视频（可选尾帧控制，本地）。"""
    if config.is_prepare():
        model = Wan2I2VModel()
    else:
        model = Wan2I2VModel.load()
    video = Wan2ImageToVideo(config("Generate Video"), model, image, prompt, negative_prompt, end_image)
    return Video("mp4", video, fps=16)


@workflow
def img2vid_hunyuan(image: Image, prompt: Prompt) -> Video:
    """HunyuanVideo I2V-720p 图生视频（本地）。"""
    if config.is_prepare():
        model = HunyuanImageToVideoModel()
    else:
        model = HunyuanImageToVideoModel.load()
    video = HunyuanImageToVideo(config("Generate Video"), model, image, prompt)
    return Video("mp4", video, fps=24)


@workflow
def txt2vid_cogvideo(prompt: Prompt, negative_prompt: Prompt) -> Video:
    """CogVideoX-5B 文生视频（本地，低显存选择）。"""
    if config.is_prepare():
        model = CogVideoModel()
    else:
        model = CogVideoModel.load()
    video = CogVideoTextToVideo(config("Generate Video"), model, prompt, negative_prompt)
    return Video("mp4", video, fps=8)


@workflow
def txt2vid_wan22(prompt: Prompt, negative_prompt: Prompt) -> Video:
    """Wan 2.2-TI2V-5B 文生视频（本地，推荐 24GB+ 显存，diffsynth 1.1.9）。"""
    if config.is_prepare():
        model = Wan22TI2VModel()
    else:
        model = Wan22TI2VModel.load()
    video = Wan22TextToVideo(config("Generate Video"), model, prompt, negative_prompt)
    return Video("mp4", video, fps=16)


@workflow
def img2vid_wan22(image: Image, prompt: Prompt, negative_prompt: Prompt, end_image: Image = None) -> Video:
    """Wan 2.2-TI2V-5B 图生视频（可选尾帧，本地，推荐 24GB+ 显存）。"""
    if config.is_prepare():
        model = Wan22TI2VModel()
    else:
        model = Wan22TI2VModel.load()
    video = Wan22ImageToVideo(config("Generate Video"), model, image, prompt, negative_prompt, end_image)
    return Video("mp4", video, fps=16)


@workflow
def txt2vid_wan22_a14b(prompt: Prompt, negative_prompt: Prompt) -> Video:
    """Wan 2.2-T2V-A14B 文生视频（MoE 双专家，建议 48GB+ 显存）。"""
    if config.is_prepare():
        model = Wan22T2VA14BModel()
    else:
        model = Wan22T2VA14BModel.load()
    video = Wan22T2VA14BTextToVideo(config("Generate Video"), model, prompt, negative_prompt)
    return Video("mp4", video, fps=16)


@workflow
def img2vid_wan22_a14b(image: Image, prompt: Prompt, negative_prompt: Prompt, end_image: Image = None) -> Video:
    """Wan 2.2-I2V-A14B 图生视频（可选尾帧，建议 48GB+ 显存）。"""
    if config.is_prepare():
        model = Wan22I2VA14BModel()
    else:
        model = Wan22I2VA14BModel.load()
    video = Wan22I2VA14BImageToVideo(config("Generate Video"), model, image, prompt, negative_prompt, end_image)
    return Video("mp4", video, fps=16)


@workflow
def txt2vid_ltx25(prompt: Prompt, negative_prompt: Prompt) -> Video:
    """LTX-2.5 文生视频（独立 LTX venv + 官方 ltx_pipelines，约 66GiB 权重）。"""
    video = LTX2TextToVideo(config("Generate Video"), prompt, negative_prompt)
    return Video("mp4", video, fps=24)


@workflow
def img2vid_ltx25(image: Image, prompt: Prompt, negative_prompt: Prompt) -> Video:
    """LTX-2.5 图生视频（需全量 dev 权重，独立 LTX venv）。"""
    video = LTX2ImageToVideo(config("Generate Video"), image, prompt, negative_prompt)
    return Video("mp4", video, fps=24)


@workflow
def txt2vid_h3(prompt: Prompt) -> Video:
    """MiniMax H3 文生视频（33B 全模态 DiT，768p + 原生音频，独立 H3 venv）。"""
    video = H3TextToVideo(config("Generate Video"), prompt)
    return Video("mp4", video, fps=24)


@workflow
def img2vid_h3(image: Image, prompt: Prompt, last_image: Image = None) -> Video:
    """MiniMax H3 图生视频（fl2va，可选尾帧，768p + 原生音频，独立 H3 venv）。"""
    video = H3ImageToVideo(config("Generate Video"), image, prompt, last_image)
    return Video("mp4", video, fps=24)
