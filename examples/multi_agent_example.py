#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整示例：使用 DeepAgents 多代理协作进行市场研究

这个示例展示了 DeepAgents 框架的核心功能：
1. 创建多个专业化的子代理
2. 主代理协调子代理工作
3. 任务自动分解和规划
4. 报告生成和保存

运行方式:
    uv run examples/multi_agent_example.py
"""

import os
import sys
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

from deepagents import create_deep_agent, CompiledSubAgent
from langchain_core.prompts import ChatPromptTemplate

from src.llm import get_llm
from src.tools import web_search, analyze_market_data, save_report
from src.agents import ResearcherAgent, AnalystAgent, WriterAgent
from src.core.logger import logger


def create_subagent(agent_class, llm) -> CompiledSubAgent:
    """创建子代理"""
    agent = agent_class(llm=llm)
    return agent.to_compiled_subagent()


def run_multi_agent_research():
    """运行多代理协作的市场研究"""

    # 获取 LLM 模型
    llm = get_llm()
    logger.info("LLM 模型初始化完成")

    # 创建子代理
    logger.info("创建子代理...")
    researcher = create_subagent(ResearcherAgent, llm)
    analyst = create_subagent(AnalystAgent, llm)
    writer = create_subagent(WriterAgent, llm)

    subagents = [researcher, analyst, writer]
    logger.info(f"已创建 {len(subagents)} 个子代理")

    # 主代理系统提示词
    system_prompt = """你是一位专业的市场研究总监，负责协调团队完成高质量的市场研究报告。

## 团队成员

### 1. 研究员 (researcher)
- 专长：信息收集、市场调研、数据获取
- 使用场景：需要收集原始市场信息时

### 2. 分析师 (analyst)
- 专长：数据分析、趋势预测、竞争分析
- 使用场景：需要深度分析数据或市场趋势时

### 3. 报告撰写员 (writer)
- 专长：报告撰写、信息整合、文档生成
- 使用场景：需要生成最终报告时

## 工作流程

1. 使用 write_todos 工具规划任务
2. 委托研究员收集信息
3. 委托分析师进行数据分析
4. 委托撰写员生成最终报告

请根据用户需求，合理分配任务给各个子代理。
"""

    # 创建主代理
    logger.info("创建主代理...")
    agent = create_deep_agent(
        model=llm,
        subagents=subagents,
        system_prompt=system_prompt,
        tools=[web_search, analyze_market_data, save_report],
    )
    logger.info("主代理创建完成")

    # 研究主题
    query = """
请帮我完成以下市场研究任务：

研究主题：中国人工智能芯片市场分析

要求：
1. 收集中国AI芯片市场的最新数据和趋势
2. 分析主要厂商和竞争格局
3. 评估市场机会和风险
4. 生成完整的市场研究报告
"""

    # 执行研究
    logger.info(f"开始研究: {query[:50]}...")
    result = agent.invoke({
        "messages": [{"role": "user", "content": query}]
    })

    # 输出结果
    final_response = result["messages"][-1].content
    print("\n" + "=" * 70)
    print("📊 市场研究报告")
    print("=" * 70)
    print(final_response)
    print("=" * 70)

    return final_response


if __name__ == "__main__":
    print("🤖 X-DeepAgents 多代理协作示例")
    print("=" * 70)

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
        print("   请复制 .env.example 为 .env 并填入：DEEPSEEK / KIMI / GLM / ALIYUN / DOUBAO 之一")
        exit(1)

    # 检查搜索 API
    if not os.environ.get("TAVILY_API_KEY"):
        print("⚠️  提示: 未配置 TAVILY_API_KEY，将使用模拟数据")

    # 运行研究
    try:
        run_multi_agent_research()
    except Exception as e:
        logger.error(f"研究执行失败: {e}")
        print(f"\n❌ 执行失败: {e}")
        raise
