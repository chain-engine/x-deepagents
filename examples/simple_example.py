#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单示例：使用 DeepAgents 进行市场研究

这个示例展示了如何使用 DeepAgents 框架的基本功能：
1. 创建带有搜索工具的代理
2. 执行研究任务
3. 生成报告

运行方式:
    uv run examples/simple_example.py
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 让本地包导入在运行 `uv run examples/*.py` 时也可用：
# - `src.*` 来自项目根目录下的 `src/`
# - `src.core.*` 来自项目根目录下的 `src/core/`
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(project_root, "src")
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from deepagents import create_deep_agent
from src.llm import get_llm
from src.tools import web_search, save_report
from src.core.logger import logger


def run_simple_research():
    """运行简单的市场研究示例"""

    # 获取 LLM 模型
    llm = get_llm()
    logger.info("LLM 模型初始化完成")

    # 定义系统提示词
    system_prompt = """你是一位专业的市场研究专家。

## 可用工具
- web_search: 搜索网络获取最新市场信息
- save_report: 保存研究报告到文件

## 工作流程
1. 使用搜索工具收集相关市场信息
2. 整理和分析数据
3. 生成结构化的市场研究报告
4. 保存报告到文件

请确保报告专业、准确、有洞察力。
"""

    # 创建 DeepAgent
    agent = create_deep_agent(
        model=llm,
        tools=[web_search, save_report],
        system_prompt=system_prompt
    )
    logger.info("DeepAgent 创建完成")

    # 研究主题
    query = "2024年中国新能源汽车市场发展趋势分析"

    # 执行研究
    logger.info(f"开始研究: {query}")
    result = agent.invoke({
        "messages": [{"role": "user", "content": query}]
    })

    # 输出结果
    final_response = result["messages"][-1].content
    print("\n" + "=" * 60)
    print("📊 研究结果")
    print("=" * 60)
    print(final_response)
    print("=" * 60)

    return final_response


async def run_async_research():
    """异步研究示例"""
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_simple_research)


if __name__ == "__main__":
    print("🚀 X-DeepAgents 简单示例")
    print("=" * 60)

    # 检查 API 配置（openai 当前不支持）
    supported_api_keys = [
        "DEEPSEEK_API_KEY",
        "KIMI_API_KEY",
        "GLM_API_KEY",
        "ALIYUN_API_KEY",
        "DOUBAO_API_KEY",
    ]
    if not any(os.environ.get(k) for k in supported_api_keys):
        print("⚠️  警告: 未检测到可用 API 密钥")
        print("   复制 .env.example 为 .env 并填入：DEEPSEEK / KIMI / GLM / ALIYUN / DOUBAO 之一")
        exit(1)

    # 运行研究
    run_simple_research()
