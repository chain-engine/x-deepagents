#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
子代理模块
实现专业化的子代理（研究、分析、写作）
"""

from typing import Any
from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel
from langchain.agents import create_agent as create_langchain_agent
from deepagents import CompiledSubAgent

from src.core.config import settings
from src.core.logger import get_logger
from src.llm import get_llm
from src.tools import web_search, analyze_market_data, save_report

logger = get_logger(__name__)


class BaseSubAgent(ABC):
    """子代理基类"""

    def __init__(self, llm: BaseChatModel | None = None):
        self.llm = llm or get_llm()
        self._agent = None

    @property
    @abstractmethod
    def name(self) -> str:
        """代理名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """代理描述"""
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """系统提示词"""
        pass

    @property
    @abstractmethod
    def tools(self) -> list:
        """可用工具列表"""
        pass

    def create_agent(self) -> Any:
        """创建代理实例"""
        # LangChain >= 1.x 已移除 `AgentExecutor/create_tool_calling_agent` 的导出，
        # 改用 `langchain.agents.create_agent` 来创建“带工具调用”的 agent runnable。
        return create_langchain_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=self.system_prompt,
            debug=self.verbose if hasattr(self, "verbose") else False,
        )

    def to_compiled_subagent(self) -> CompiledSubAgent:
        """转换为 CompiledSubAgent 格式"""
        agent = self.create_agent()
        return CompiledSubAgent(
            name=self.name,
            description=self.description,
            runnable=agent,
        )


class ResearcherAgent(BaseSubAgent):
    """
    研究员代理
    负责收集市场信息和数据
    """

    @property
    def name(self) -> str:
        return "researcher"

    @property
    def description(self) -> str:
        return "专业市场研究员，负责收集行业信息、市场数据和竞争情报"

    @property
    def system_prompt(self) -> str:
        return """你是一位专业的市场研究专家，负责收集和分析市场信息。

## 职责
1. 使用搜索工具收集相关的市场信息
2. 整理关键数据点，包括市场规模、增长率、主要参与者等
3. 识别市场趋势和潜在机会
4. 确保信息的准确性和时效性

## 工作流程
1. 明确研究目标和范围
2. 使用搜索工具收集信息
3. 整理和验证数据
4. 输出结构化的研究结果

## 输出格式
请以结构化的方式输出研究结果，包括：
- 市场概况
- 关键数据点
- 主要发现
- 数据来源

## 注意事项
- 优先使用权威数据源
- 标注数据的时效性
- 对矛盾信息进行交叉验证
"""

    @property
    def tools(self) -> list:
        return [web_search]


class AnalystAgent(BaseSubAgent):
    """
    数据分析师代理
    负责分析市场数据和趋势
    """

    @property
    def name(self) -> str:
        return "analyst"

    @property
    def description(self) -> str:
        return "数据分析专家，负责市场趋势分析、竞争分析和投资分析"

    @property
    def system_prompt(self) -> str:
        return """你是一位专业的数据分析师，负责分析市场数据和趋势。

## 职责
1. 分析市场数据，识别趋势和模式
2. 进行竞争分析和市场定位分析
3. 评估市场机会和风险
4. 提供数据驱动的洞察和建议

## 分析方法
1. 趋势分析：识别市场发展方向
2. 对比分析：与竞争对手或历史数据对比
3. SWOT分析：评估优势、劣势、机会、威胁
4. 预测分析：基于数据预测未来趋势

## 输出格式
请以专业的分析报告格式输出，包括：
- 执行摘要
- 关键指标分析
- 趋势解读
- 风险评估
- 可行建议

## 分析原则
- 基于数据和事实
- 区分事实和观点
- 提供可量化的指标
- 考虑多种场景和假设
"""

    @property
    def tools(self) -> list:
        return [analyze_market_data, web_search]


class WriterAgent(BaseSubAgent):
    """
    报告撰写员代理
    负责整合信息并生成最终报告
    """

    @property
    def name(self) -> str:
        return "writer"

    @property
    def description(self) -> str:
        return "专业报告撰写员，负责整合研究结果并生成高质量的市场研究报告"

    @property
    def system_prompt(self) -> str:
        return """你是一位专业的报告撰写专家，负责生成高质量的市场研究报告。

## 职责
1. 整合研究员和分析师的输出
2. 组织报告结构和逻辑
3. 撰写清晰、专业的报告内容
4. 保存最终报告到文件系统

## 报告结构
标准的市场研究报告应包含：

### 1. 执行摘要
- 研究背景和目的
- 核心发现摘要
- 关键建议

### 2. 市场概况
- 市场规模和增长
- 市场细分
- 主要参与者

### 3. 市场分析
- 趋势分析
- 竞争格局
- SWOT分析

### 4. 风险与机会
- 主要风险因素
- 市场机会

### 5. 结论与建议
- 核心结论
- 可行建议
- 后续研究建议

## 写作原则
- 使用专业、客观的语言
- 引用数据来源
- 使用图表说明复杂数据
- 确保逻辑清晰
- 面向决策者需求
"""

    @property
    def tools(self) -> list:
        return [save_report]


class SubAgentFactory:
    """子代理工厂"""

    _agents = {
        "researcher": ResearcherAgent,
        "analyst": AnalystAgent,
        "writer": WriterAgent,
    }

    @classmethod
    def create(cls, agent_type: str, llm: BaseChatModel | None = None) -> BaseSubAgent:
        """创建指定类型的子代理"""
        if agent_type not in cls._agents:
            raise ValueError(f"未知的代理类型: {agent_type}")

        agent_class = cls._agents[agent_type]
        return agent_class(llm=llm)

    @classmethod
    def create_all(cls, llm: BaseChatModel | None = None) -> list[CompiledSubAgent]:
        """创建所有子代理"""
        subagents = []
        for agent_type in cls._agents:
            agent = cls.create(agent_type, llm=llm)
            subagents.append(agent.to_compiled_subagent())
            logger.info(f"创建子代理: {agent.name}")
        return subagents


# 便捷导出
def get_researcher_agent(llm: BaseChatModel | None = None) -> CompiledSubAgent:
    """获取研究员代理"""
    return ResearcherAgent(llm=llm).to_compiled_subagent()


def get_analyst_agent(llm: BaseChatModel | None = None) -> CompiledSubAgent:
    """获取分析师代理"""
    return AnalystAgent(llm=llm).to_compiled_subagent()


def get_writer_agent(llm: BaseChatModel | None = None) -> CompiledSubAgent:
    """获取撰写员代理"""
    return WriterAgent(llm=llm).to_compiled_subagent()
