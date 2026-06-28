#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 提供者模块
支持多种 LLM 后端（DeepSeek、kimi2.5、glm4.7、阿里云、豆包等）
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Optional
from enum import Enum

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


class LLMProvider(str, Enum):
    """支持的 LLM 提供者"""
    DEEPSEEK = "deepseek"
    KIMI_2_5 = "kimi2.5"
    GLM_4_7 = "glm4.7"
    ALIYUN = "aliyun"
    DOUBAO = "doubao"


class LLMConfig(BaseModel):
    """LLM 配置模型"""
    provider: LLMProvider = LLMProvider.DEEPSEEK
    model_name: str = "deepseek-chat"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 4096


class BaseLLMProvider(ABC):
    """LLM 提供者基类"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._model: Optional[BaseChatModel] = None

    @abstractmethod
    def create_model(self) -> BaseChatModel:
        """创建 LLM 模型实例"""
        pass

    @property
    def model(self) -> BaseChatModel:
        """获取模型实例（懒加载）"""
        if self._model is None:
            self._model = self.create_model()
        return self._model


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek 提供者"""

    def create_model(self) -> BaseChatModel:
        from langchain_deepseek import ChatDeepSeek

        api_key = self.config.api_key or os.environ.get("DEEPSEEK_API_KEY")
        api_base = self.config.api_base or os.environ.get("DEEPSEEK_API_BASE")

        logger.info(f"初始化 DeepSeek 模型: {self.config.model_name}")

        return ChatDeepSeek(
            model=self.config.model_name,
            api_key=api_key,
            base_url=api_base,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

class KimiProvider(BaseLLMProvider):
    """kimi2.5 提供者（OpenAI兼容接口）"""

    def create_model(self) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        api_key = self.config.api_key or os.environ.get("KIMI_API_KEY")
        api_base = self.config.api_base or os.environ.get("KIMI_API_BASE", "https://api.moonshot.cn/v1")

        logger.info(f"初始化 Kimi 模型: {self.config.model_name}")

        return ChatOpenAI(
            model=self.config.model_name,
            api_key=api_key,
            base_url=api_base,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )


class GlmProvider(BaseLLMProvider):
    """glm4.7 提供者（OpenAI兼容接口）"""

    def create_model(self) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        api_key = self.config.api_key or os.environ.get("GLM_API_KEY")
        api_base = self.config.api_base or os.environ.get("GLM_API_BASE", "https://open.bigmodel.cn/api/paas/v4")

        logger.info(f"初始化 GLM 模型: {self.config.model_name}")

        return ChatOpenAI(
            model=self.config.model_name,
            api_key=api_key,
            base_url=api_base,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )


class AliyunProvider(BaseLLMProvider):
    """阿里云通义千问提供者"""

    def create_model(self) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        api_key = self.config.api_key or os.environ.get("ALIYUN_API_KEY")
        api_base = self.config.api_base or os.environ.get("ALIYUN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")

        logger.info(f"初始化阿里云模型: {self.config.model_name}")

        return ChatOpenAI(
            model=self.config.model_name,
            api_key=api_key,
            base_url=api_base,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )


class DoubaoProvider(BaseLLMProvider):
    """火山引擎豆包提供者"""

    def create_model(self) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        api_key = self.config.api_key or os.environ.get("DOUBAO_API_KEY")
        api_base = self.config.api_base or os.environ.get("DOUBAO_API_BASE")

        logger.info(f"初始化豆包模型: {self.config.model_name}")

        return ChatOpenAI(
            model=self.config.model_name,
            api_key=api_key,
            base_url=api_base,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )


# 提供者映射
PROVIDERS: dict[LLMProvider, type[BaseLLMProvider]] = {
    LLMProvider.DEEPSEEK: DeepSeekProvider,
    LLMProvider.KIMI_2_5: KimiProvider,
    LLMProvider.GLM_4_7: GlmProvider,
    LLMProvider.ALIYUN: AliyunProvider,
    LLMProvider.DOUBAO: DoubaoProvider,
}

PROVIDER_SETTINGS: dict[LLMProvider, dict[str, str]] = {
    LLMProvider.DEEPSEEK: {"model_env": "DEEPSEEK_MODEL_NAME", "default_model": "deepseek-chat"},
    LLMProvider.KIMI_2_5: {"model_env": "KIMI_MODEL_NAME", "default_model": "kimi2.5"},
    LLMProvider.GLM_4_7: {"model_env": "GLM_MODEL_NAME", "default_model": "glm4.7"},
    LLMProvider.ALIYUN: {"model_env": "ALIYUN_MODEL_NAME", "default_model": "qwen-turbo"},
    LLMProvider.DOUBAO: {"model_env": "DOUBAO_MODEL_NAME", "default_model": "doubao-pro-32k-241215"},
}


def get_llm(
    provider: Optional[LLMProvider] = None,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    **kwargs
) -> BaseChatModel:
    """
    获取 LLM 模型实例

    Args:
        provider: LLM 提供者，默认从环境变量读取
        model_name: 模型名称
        temperature: 温度参数
        **kwargs: 其他配置参数

    Returns:
        BaseChatModel: LLM 模型实例
    """
    # 从环境变量或配置获取默认提供者
    provider_name = provider or os.environ.get("LLM_PROVIDER", "deepseek")
    try:
        provider_enum = LLMProvider(provider_name)
    except ValueError as e:
        raise ValueError(
            f"不支持的 LLM 提供者: {provider_name}。"
            f"openai 当前不支持；支持: deepseek, kimi2.5, glm4.7, aliyun, doubao"
        ) from e

    provider_setting = PROVIDER_SETTINGS[provider_enum]
    resolved_model_name = model_name or os.environ.get(provider_setting["model_env"]) or provider_setting["default_model"]

    # 构建配置
    config = LLMConfig(
        provider=provider_enum,
        model_name=resolved_model_name,
        temperature=temperature or settings.TEMPERATURE,
        **kwargs,
    )

    # 获取提供者类并创建实例
    provider_class = PROVIDERS.get(provider_enum)
    if provider_class is None:
        raise ValueError(f"不支持的 LLM 提供者: {provider_enum}")

    provider_instance = provider_class(config)
    return provider_instance.model


# 默认 LLM 实例（懒加载）
_default_llm: Optional[BaseChatModel] = None


def get_default_llm() -> BaseChatModel:
    """获取默认 LLM 实例"""
    global _default_llm
    if _default_llm is None:
        _default_llm = get_llm()
    return _default_llm
