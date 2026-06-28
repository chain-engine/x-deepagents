#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主代理协调器
使用 DeepAgents 创建智能市场研究报告生成系统
"""

from typing import Any, Optional
import asyncio

from langchain_core.language_models import BaseChatModel
from deepagents import create_deep_agent

from src.core.config import settings
from src.core.logger import get_logger
from src.llm import get_llm
from src.agents import SubAgentFactory
from src.tools import web_search, analyze_market_data, save_report

logger = get_logger(__name__)


# 主代理系统提示词
MAIN_AGENT_SYSTEM_PROMPT = """
# 角色定位
你是一位专业的市场研究总监，负责协调团队完成高质量的市场研究报告。
你管理着一个由三个专业子代理组成的团队：研究员、分析师和报告撰写员。

# 团队成员

## 1. 研究员 (researcher)
- **专长**：信息收集、市场调研、数据获取
- **能力**：使用搜索工具收集行业信息、市场数据和竞争情报
- **适用场景**：需要收集原始市场信息时

## 2. 分析师 (analyst)
- **专长**：数据分析、趋势预测、竞争分析
- **能力**：分析市场数据、识别趋势、评估机会和风险
- **适用场景**：需要深度分析数据或市场趋势时

## 3. 报告撰写员 (writer)
- **专长**：报告撰写、信息整合、文档生成
- **能力**：整合研究结果、撰写专业报告、保存报告文件
- **适用场景**：需要生成最终报告时

# 工作流程

当收到用户的市场研究请求时，请按以下流程协调工作：

## 第一阶段：任务规划
1. 分析用户需求，明确研究目标
2. 使用 `write_todos` 工具制定详细的研究计划
3. 确定需要调用的子代理和执行顺序

## 第二阶段：信息收集
1. 委托研究员收集相关市场信息
2. 确保收集到足够的数据支持分析
3. 整理和验证收集到的信息

## 第三阶段：数据分析
1. 委托分析师进行深度数据分析
2. 识别市场趋势和关键洞察
3. 评估机会和风险

## 第四阶段：报告生成
1. 委托报告撰写员整合所有信息
2. 生成结构化的市场研究报告
3. 保存报告到文件系统

# 任务分配原则

1. **复杂多步骤任务**：使用 `task` 工具委托给相应的子代理
2. **独立任务**：可以并行委托多个子代理同时工作
3. **简单查询**：直接使用工具或自身知识回答

# 输出规范

生成的市场研究报告应包含：
- 执行摘要
- 市场概况（规模、增长、细分）
- 竞争格局分析
- 趋势分析
- SWOT分析
- 风险与机会
- 结论与建议

# 行为准则

1. 始终保持专业和客观的态度
2. 基于数据和事实进行分析
3. 标注信息来源和时效性
4. 对不确定性进行说明
5. 生成可直接使用的专业报告
"""


class MarketResearchAgent:
    """
    智能市场研究代理

    使用 DeepAgents 框架构建的多智能体系统，
    能够自动协调完成市场研究报告的生成。
    """

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        verbose: bool = True
    ):
        """
        初始化市场研究代理

        Args:
            llm: 语言模型实例，默认使用配置的模型
            verbose: 是否输出详细日志
        """
        self.llm = llm or get_llm()
        self.verbose = verbose
        self._agent = None

    def _create_agent(self) -> Any:
        """创建 DeepAgent 实例"""
        logger.info("正在创建市场研究代理...")

        # 创建所有子代理
        subagents = SubAgentFactory.create_all(self.llm)
        logger.info(f"已创建 {len(subagents)} 个子代理")

        # 创建主代理
        agent = create_deep_agent(
            model=self.llm,
            subagents=subagents,
            system_prompt=MAIN_AGENT_SYSTEM_PROMPT,
            tools=[web_search, analyze_market_data, save_report],  # 主代理也可以直接使用这些工具
        )

        logger.info("市场研究代理创建完成")
        return agent

    @property
    def agent(self) -> Any:
        """获取代理实例（懒加载）"""
        if self._agent is None:
            self._agent = self._create_agent()
        return self._agent

    def research(self, query: str) -> dict:
        """
        执行市场研究

        Args:
            query: 研究查询或主题

        Returns:
            dict: 研究结果
        """
        logger.info(f"开始市场研究: {query}")

        # 构建输入消息
        input_message = {
            "messages": [{
                "role": "user",
                "content": f"""请帮我完成以下市场研究任务：

{query}

请按照完整的研究流程执行：
1. 收集相关市场信息
2. 分析市场趋势和数据
3. 生成结构化的市场研究报告
4. 保存报告到文件

谢谢！"""
            }]
        }

        # 调用代理
        result = self.agent.invoke(input_message)

        # 提取最终响应
        final_message = result.get("messages", [])[-1] if result.get("messages") else None

        return {
            "query": query,
            "response": final_message.content if final_message else "",
            "full_result": result
        }

    async def aresearch(self, query: str) -> dict:
        """
        异步执行市场研究

        Args:
            query: 研究查询或主题

        Returns:
            dict: 研究结果
        """
        # 在异步环境中运行同步方法
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.research, query)

    def stream_research(self, query: str):
        """
        流式输出研究过程

        Args:
            query: 研究查询或主题

        Yields:
            研究过程中的消息
        """
        logger.info(f"开始流式市场研究: {query}")

        input_message = {
            "messages": [{
                "role": "user",
                "content": f"请帮我完成以下市场研究任务：\n\n{query}"
            }]
        }

        # 流式调用代理
        for event in self.agent.stream(input_message):
            yield event


def create_market_research_agent(
    llm: BaseChatModel | None = None,
    verbose: bool = True
) -> MarketResearchAgent:
    """
    创建市场研究代理的便捷函数

    Args:
        llm: 语言模型实例
        verbose: 是否输出详细日志

    Returns:
        MarketResearchAgent: 市场研究代理实例
    """
    return MarketResearchAgent(llm=llm, verbose=verbose)


# 简单研究函数（不使用子代理，直接使用工具）
def simple_research(query: str, llm: BaseChatModel | None = None) -> str:
    """
    简单研究函数

    不使用子代理，直接创建一个带有搜索工具的 DeepAgent。

    Args:
        query: 研究查询
        llm: 语言模型实例

    Returns:
        str: 研究结果
    """
    llm = llm or get_llm()

    simple_prompt = """你是一位专业的研究员，负责对给定主题进行深入研究并生成报告。

## 可用工具
- web_search: 搜索网络获取最新信息
- save_report: 保存报告到文件

## 工作流程
1. 使用搜索工具收集相关信息
2. 整理和分析数据
3. 生成结构化的研究报告
4. 保存报告

请确保报告专业、准确、有洞察力。
"""

    agent = create_deep_agent(
        model=llm,
        tools=[web_search, save_report],
        system_prompt=simple_prompt
    )

    result = agent.invoke({
        "messages": [{"role": "user", "content": query}]
    })

    return result["messages"][-1].content
