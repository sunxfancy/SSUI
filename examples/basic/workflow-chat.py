from typing import List, Tuple

from ssui import workflow
from ssui.config import SSUIConfig
from ssui_llm.Qwen import Chat, QwenModel

config = SSUIConfig()


@workflow
def chat(model: QwenModel, prompt: str) -> Tuple[str, List[Tuple[str, str]]]:
    return Chat(config("Chat"), model, prompt)
