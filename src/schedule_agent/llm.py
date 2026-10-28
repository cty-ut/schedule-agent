"""模型接入：任何兼容 OpenAI Chat Completions + tools 的服务（默认 DeepSeek）。

统一返回 OpenAI 格式的 assistant 消息 dict，便于直接追加进对话历史。
"""
from __future__ import annotations

import os
from typing import Protocol


class ChatModel(Protocol):
    name: str

    def chat(self, messages: list[dict], tools: list[dict]) -> dict: ...


class OpenAICompatibleModel:
    def __init__(self, model: str | None = None, base_url: str | None = None, api_key: str | None = None,
                 temperature: float = 0.0, timeout: float = 60.0):
        from openai import OpenAI

        api_key = api_key or os.getenv("LLM_API_KEY")
        if not api_key:
            raise RuntimeError("未配置 LLM_API_KEY；请复制 .env.example 为 .env 并填写，或使用 --mock 离线运行")
        self.name = model or os.getenv("LLM_MODEL", "deepseek-chat")
        self.temperature = temperature
        self.client = OpenAI(api_key=api_key, base_url=base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
                             timeout=timeout, max_retries=2)

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        resp = self.client.chat.completions.create(
            model=self.name, messages=messages, tools=tools, tool_choice="auto", temperature=self.temperature,
        )
        msg = resp.choices[0].message
        out: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            out["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        return out
