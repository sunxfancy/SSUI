import os
import requests
from pathlib import Path
from tqdm import tqdm

# 配置模型信息
MODEL_CONFIGS = {
    "sd1": {
        "url": "https://civitai.com/api/download/models/425083?type=Model&format=SafeTensor&size=full&fp=fp16",
        "path": "models/sd1/ReVAnimated.safetensors",
    },
    "sdxl": {
        "url": "https://civitai.com/api/download/models/384264?type=Model&format=SafeTensor&size=full&fp=fp16",
        "path": "models/sdxl/AnythingXL.safetensors",
    },
    "flux": {
        "model": {
            "url": "https://huggingface.co/InvokeAI/flux_schnell/resolve/main/transformer/bnb_nf4/flux1-schnell-bnb_nf4.safetensors?download=true",
            "path": "models/flux/flux1-schnell-bnb_nf4.safetensors",
        },
        "t5_encoder": {
            "url": "https://huggingface.co/InvokeAI/t5-v1_1-xxl/resolve/main/bnb_llm_int8/text_encoder_2/bnb_llm_int8_model.safetensors?download=true",
            "path": "models/any/t5_encoder/bnb_llm_int8_model.safetensors",
        },
        "clip": {
            "url": "https://huggingface.co/InvokeAI/clip-vit-large-patch14-text-encoder/resolve/main/bfloat16/text_encoder/model.safetensors?download=true",
            "path": "models/any/clip_embed/clip-vit-large-patch14.safetensors",
        }
    },
}

# 检查是否应该运行慢速测试
def should_run_slow_tests() -> bool:
    return os.environ.get("RUN_SLOW_TESTS", "0").lower() in ("1", "true", "yes")

# 获取测试数据根目录
def get_test_data_dir() -> Path:
    # 从环境变量获取，或使用默认位置
    return Path(os.environ.get("TEST_DATA_DIR", os.path.expanduser("~/.ssui_test_data")))

# 按需下载模型
def download_if_needed(model_key: str, sub_key: str | None = None) -> Path:
    data_dir = get_test_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    
    if sub_key:
        config = MODEL_CONFIGS[model_key][sub_key]
    else:
        config = MODEL_CONFIGS[model_key]
    
    dest_path = data_dir / config["path"]
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not dest_path.exists():
        print(f"下载模型: {dest_path}")
        url = config["url"]
        
        # 下载文件
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get("content-length", 0))
        
        with open(dest_path, "wb") as f, tqdm(
            total=total_size, unit="B", unit_scale=True
        ) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))
    
    return dest_path 

