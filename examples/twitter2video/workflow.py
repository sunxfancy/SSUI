from ssui import workflow, Prompt, Image, Video
from ssui.annotation import param
from ssui.config import SSUIConfig
from ssui.controller import Input
from ssui_video.Wan import WanVideoModel, WanImageTextToVideo
from ssui_image.Flux import FluxModel, FluxClip, FluxLatent, FluxDenoise, FluxLatentDecode
from typing import List
import tweepy
from datetime import datetime, timedelta
import requests
import json
from ssui_voice.Cosyvoice import CosyvoiceModel, CosyvoiceGenerate

config = SSUIConfig()

@param("CONSUMER_KEY", Input("Twitter Consumer Key..."), default="")
@param("ACCESS_TOKEN", Input("Twitter Access Token..."), default="")
def get_latest_tweet(username: str) -> str:
    """获取指定Twitter用户的最新推文"""
    # 这里需要配置Twitter API的认证信息
    auth = tweepy.OAuthHandler("YOUR_CONSUMER_KEY", config["CONSUMER_KEY"])
    auth.set_access_token("YOUR_ACCESS_TOKEN", config["ACCESS_TOKEN"])
    api = tweepy.API(auth)
    
    # 获取用户最新推文
    tweets = api.user_timeline(screen_name=username, count=1)
    if tweets:
        return tweets[0].text
    return ""

@param("DEEPSEEK_API_KEY", Input("DeepSeek API Key..."), default="")
def generate_poem(tweet_content: str) -> List[str]:
    """调用DeepSeek API生成打油诗"""
    # 这里需要配置DeepSeek API的认证信息
    headers = {
        "Authorization": config['DEEPSEEK_API_KEY'],
        "Content-Type": "application/json"
    }
    
    prompt = """请根据以下推文内容生成一首讽刺风格的打油诗，每句诗都要押韵，并且要幽默有趣。 
    最后请仅输出这首诗，不要输出除此以外任何其他内容，不要标点，使用回车换行即可：""" + tweet_content
    
    response = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers=headers,
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}]
        }
    )
    
    poem = response.json()["choices"][0]["message"]["content"]
    # 将诗分成句子
    return [line.strip() for line in poem.split('\n') if line.strip()]

@workflow
def tweet2poem_image(model: FluxModel, poem_line: str) -> Image:
    """将诗句转换为图片"""
    positive = Prompt(f"生成一张与以下诗句相关的图片，风格要生动有趣：{poem_line}")
    negative = Prompt("模糊的，低质量的，扭曲的")
    
    positive, negative = FluxClip(config("Prompt To Condition"), model, positive, negative)
    latent = FluxLatent(config("Create Empty Latent"))
    latent = FluxDenoise(config("Denoise"), model, latent, positive, negative)
    return FluxLatentDecode(config("Latent to Image"), model, latent)

@workflow
def image2video(image: Image, prompt: Prompt, negative_prompt: Prompt) -> Video:
    """将图片序列转换为视频"""
    model = WanVideoModel()
    video = WanImageTextToVideo(config("Generate Video"), model, image, prompt, negative_prompt)
    return Video("mp4", video, fps=30)

@workflow
def txt2voice(text: str) -> Voice:
    """将文本转换为语音"""
    model = CosyvoiceModel()
    voice = CosyvoiceGenerate(config("Text to Speech"), model, text)
    return Voice("mp3", voice, text, fps=16000)

@workflow
def twitter2video(username: str) -> Video:
    """主工作流：从Twitter到视频的转换"""
    # 1. 获取最新推文
    tweet_content = get_latest_tweet(username)
    
    # 2. 生成打油诗
    poem_lines = generate_poem(tweet_content)
    
    # 3. 为每句诗生成图片
    model = FluxModel()
    images = [tweet2poem_image(model, line) for line in poem_lines]
    
    # 4. 生成视频
    prompt = Prompt("生成一个流畅的视频，展示诗句的意境")
    negative_prompt = Prompt("卡顿的，不连贯的，低质量的")
    videos = [image2video(image, prompt, negative_prompt) for image in images]

    # 5. 配音
    voices = [txt2voice(poem_line) for poem_line in poem_lines]

    # 6. 合成视频和语音
    videos = [video.add_audio(voice) for video, voice in zip(videos, voices)]

    return videos
