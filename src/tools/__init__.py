#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具集模块
提供搜索、数据分析等工具
"""

from typing import Literal
import os
import json
import asyncio
from datetime import datetime
from pathlib import Path

import httpx
from tavily import TavilyClient
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


# ==================== 搜索工具 ====================

class SearchResult(BaseModel):
    """搜索结果模型"""
    title: str
    url: str
    content: str
    score: float = 0.0
    published_date: str | None = None


class SearchResponse(BaseModel):
    """搜索响应模型"""
    query: str
    results: list[SearchResult]
    total_results: int
    search_time: float


def web_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
) -> dict:
    """
    网络搜索工具

    使用 Tavily API 执行网络搜索，支持多种搜索主题。

    Args:
        query: 搜索查询关键词
        max_results: 最大返回结果数，默认5
        topic: 搜索主题类型（general/news/finance）
        include_raw_content: 是否包含原始网页内容

    Returns:
        dict: 搜索结果字典
    """
    logger.info(f"执行网络搜索: query='{query}', max_results={max_results}, topic={topic}")

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        logger.warning("TAVILY_API_KEY 未配置，返回模拟数据")
        return _get_mock_search_results(query, max_results)

    try:
        client = TavilyClient(api_key=api_key)
        result = client.search(
            query=query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic,
        )

        logger.info(f"搜索完成，返回 {len(result.get('results', []))} 个结果")
        return result

    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return _get_mock_search_results(query, max_results)


def _get_mock_search_results(query: str, max_results: int) -> dict:
    """生成模拟搜索结果（用于测试）"""
    mock_results = []
    for i in range(min(max_results, 3)):
        mock_results.append({
            "title": f"搜索结果 {i+1}: {query}",
            "url": f"https://example.com/result/{i+1}",
            "content": f"这是关于 '{query}' 的模拟搜索结果内容。包含了相关的市场信息和分析数据。",
            "score": 0.95 - i * 0.1,
        })

    return {
        "query": query,
        "results": mock_results,
        "response_time": 0.5,
    }


# ==================== 数据分析工具 ====================

class DataPoint(BaseModel):
    """数据点模型"""
    label: str
    value: float
    change: float | None = None
    unit: str = ""


class AnalysisResult(BaseModel):
    """分析结果模型"""
    metric: str
    data_points: list[DataPoint]
    summary: str
    trend: Literal["up", "down", "stable"] = "stable"


def analyze_market_data(
    data: list[dict],
    metric_name: str,
    analysis_type: Literal["trend", "comparison", "summary"] = "summary",
) -> dict:
    """
    市场数据分析工具

    对提供的数据进行趋势分析、对比分析或摘要分析。

    Args:
        data: 要分析的数据列表
        metric_name: 指标名称
        analysis_type: 分析类型

    Returns:
        dict: 分析结果
    """
    logger.info(f"执行数据分析: metric={metric_name}, type={analysis_type}, data_count={len(data)}")

    if not data:
        return {
            "metric": metric_name,
            "summary": "无数据可分析",
            "data_points": [],
            "trend": "stable"
        }

    # 简单的数据分析逻辑
    values = [d.get("value", 0) for d in data if isinstance(d.get("value"), (int, float))]

    if not values:
        return {
            "metric": metric_name,
            "summary": "数据格式无效",
            "data_points": [],
            "trend": "stable"
        }

    avg_value = sum(values) / len(values)
    max_value = max(values)
    min_value = min(values)

    # 计算趋势
    if len(values) >= 2:
        if values[-1] > values[0] * 1.05:
            trend = "up"
        elif values[-1] < values[0] * 0.95:
            trend = "down"
        else:
            trend = "stable"
    else:
        trend = "stable"

    summary = f"{metric_name}分析: 平均值 {avg_value:.2f}, 最高 {max_value:.2f}, 最低 {min_value:.2f}"

    return {
        "metric": metric_name,
        "summary": summary,
        "statistics": {
            "average": avg_value,
            "max": max_value,
            "min": min_value,
            "count": len(values)
        },
        "trend": trend,
        "data_points": data
    }


# ==================== 报告生成工具 ====================

def save_report(
    content: str,
    filename: str,
    format: Literal["markdown", "json", "html"] = "markdown",
) -> dict:
    """
    保存报告到文件

    Args:
        content: 报告内容
        filename: 文件名（不含扩展名）
        format: 输出格式

    Returns:
        dict: 保存结果信息
    """
    logger.info(f"保存报告: filename={filename}, format={format}")

    # 确保输出目录存在
    output_dir = Path(settings.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    extension = {"markdown": "md", "json": "json", "html": "html"}[format]
    full_filename = f"{filename}_{timestamp}.{extension}"
    file_path = output_dir / full_filename

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"报告已保存: {file_path}")

        return {
            "success": True,
            "file_path": str(file_path),
            "filename": full_filename,
            "size_bytes": len(content.encode("utf-8"))
        }

    except Exception as e:
        logger.error(f"保存报告失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def read_report(filename: str) -> dict:
    """
    读取已保存的报告

    Args:
        filename: 文件名或完整路径

    Returns:
        dict: 报告内容
    """
    logger.info(f"读取报告: filename={filename}")

    # 尝试多种路径
    possible_paths = [
        Path(filename),
        Path(settings.OUTPUT_DIR) / filename,
    ]

    for path in possible_paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                return {
                    "success": True,
                    "content": content,
                    "file_path": str(path)
                }
            except Exception as e:
                logger.error(f"读取报告失败: {e}")

    return {
        "success": False,
        "error": f"未找到报告文件: {filename}"
    }


# ==================== 工具注册 ====================

# 所有可用的工具
AVAILABLE_TOOLS = {
    "web_search": web_search,
    "analyze_market_data": analyze_market_data,
    "save_report": save_report,
    "read_report": read_report,
}


def get_tools_for_agent(tool_names: list[str] | None = None) -> list:
    """
    获取指定的工具列表

    Args:
        tool_names: 工具名称列表，如果为 None 则返回所有工具

    Returns:
        list: 工具函数列表
    """
    if tool_names is None:
        return list(AVAILABLE_TOOLS.values())

    tools = []
    for name in tool_names:
        if name in AVAILABLE_TOOLS:
            tools.append(AVAILABLE_TOOLS[name])
        else:
            logger.warning(f"未知工具: {name}")

    return tools
