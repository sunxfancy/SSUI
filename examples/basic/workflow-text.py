from typing import List, Tuple

from ssui import workflow
from ssui.config import SSUIConfig
from ssui_llm.Text import Chat, Generate, TextModel

config = SSUIConfig()


@workflow
def chat(model: TextModel, prompt: str, system_prompt: str = "") -> Tuple[str, List[Tuple[str, str]]]:
    return Chat(config("Chat"), model, prompt, system_prompt=system_prompt)


@workflow
def complete(model: TextModel, prompt: str) -> str:
    return Generate(config("Generate"), model, prompt)
