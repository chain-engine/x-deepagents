#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令行交互界面
提供友好的用户交互体验
"""

import sys
import os
from typing import Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.theme import Theme

# 添加项目根目录与 `src/` 目录到路径：
# - 让 `from src.*` 能找到位于项目根目录下的 `src/` 包
# - 让 `from src.core.*` 在直接运行脚本时可用（用于本地调试/示例）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, project_root)
sys.path.insert(0, src_dir)

from src.core.config import settings
from src.core.logger import logger
from src.agents.coordinator import MarketResearchAgent, simple_research

# 加载环境变量
load_dotenv()

# 自定义主题
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "success": "green",
    "highlight": "magenta",
})

# Windows 下默认使用的 legacy 渲染可能导致编码问题（尤其是 emoji/特殊字符）。
# 关闭 legacy_windows 与 emoji 以提升兼容性。
console = Console(theme=custom_theme, legacy_windows=False, emoji=False)


def print_banner():
    """打印欢迎横幅"""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║     X-DeepAgents - 智能市场研究报告生成系统                     ║
    ║                                                               ║
    ║     基于 LangChain DeepAgents 框架构建                         ║
    ║     支持多代理协作、任务规划、自动报告生成                        ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold cyan")


def print_help():
    """打印帮助信息"""
    help_text = """
## 使用指南

### 基本命令
- 直接输入研究主题，系统将自动完成研究和报告生成
- `help` - 显示帮助信息
- `example` - 查看示例研究主题
- `config` - 显示当前配置
- `clear` - 清空屏幕
- `quit` / `exit` - 退出程序

### 研究模式
1. **完整模式** (默认) - 使用多代理协作，适合复杂研究
2. **简单模式** - 单代理执行，适合快速查询

### 示例研究主题
- 中国新能源汽车市场分析报告
- 人工智能行业投资机会研究
- 全球半导体产业链分析
- 电商平台竞争格局研究
- SaaS行业发展趋势分析
"""
    console.print(Panel(Markdown(help_text), title="帮助", border_style="blue"))


def print_examples():
    """打印示例研究主题"""
    examples = """
## 示例研究主题

1. **行业分析**
   - "2024年中国新能源汽车市场分析报告"
   - "全球人工智能芯片市场研究报告"

2. **竞争分析**
   - "国内电商平台竞争格局分析"
   - "云计算服务商市场份额分析"

3. **趋势研究**
   - "SaaS行业发展趋势与投资机会"
   - "元宇宙产业发展前景分析"

4. **区域市场**
   - "东南亚电商市场机会分析"
   - "欧洲新能源政策对汽车产业的影响"
"""
    console.print(Panel(Markdown(examples), title="示例", border_style="green"))


def print_config():
    """打印当前配置"""
    config_text = f"""
## 当前配置

| 配置项 | 值 |
|--------|-----|
| LLM 提供者 | {settings.LLM_PROVIDER} |
| 温度参数 | {settings.TEMPERATURE} |
| 输出目录 | {settings.OUTPUT_DIR} |
| 最大信息源 | {settings.MAX_SOURCES} |
| 调试模式 | {settings.DEBUG} |
| 日志级别 | {settings.LOG_LEVEL} |
"""
    console.print(Panel(Markdown(config_text), title="配置", border_style="yellow"))


def run_research(query: str, simple_mode: bool = False):
    """
    执行市场研究

    Args:
        query: 研究查询
        simple_mode: 是否使用简单模式
    """
    console.print(f"\n[bold cyan]开始研究主题:[/] [highlight]{query}[/]\n")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("研究进行中...", total=None)

            if simple_mode:
                result = simple_research(query)
            else:
                agent = MarketResearchAgent(verbose=True)
                research_result = agent.research(query)
                result = research_result.get("response", "")

        console.print("\n[bold green]研究完成！[/]\n")
        console.print(Panel(Markdown(result), title="研究报告", border_style="green"))

        console.print(f"\n[dim]报告已保存到 {settings.OUTPUT_DIR} 目录[/]")

    except Exception as e:
        logger.error(f"研究执行失败: {e}")
        console.print(f"\n[bold red]研究执行失败: {e}[/]\n")


def interactive_mode():
    """交互模式"""
    print_banner()
    console.print("[dim]输入 'help' 查看帮助，'quit' 退出程序[/]\n")

    simple_mode = False

    while True:
        try:
            # 获取用户输入
            user_input = Prompt.ask(
                "[bold cyan]市场研究[/]",
                default=""
            ).strip()

            if not user_input:
                continue

            # 处理命令
            if user_input.lower() in ["quit", "exit", "q"]:
                console.print("\n[yellow]感谢使用，再见！[/]")
                break

            elif user_input.lower() == "help":
                print_help()

            elif user_input.lower() == "example":
                print_examples()

            elif user_input.lower() == "config":
                print_config()

            elif user_input.lower() == "clear":
                console.clear()
                print_banner()

            elif user_input.lower() == "simple":
                simple_mode = True
                console.print("[green]已切换到简单模式[/]")

            elif user_input.lower() == "full":
                simple_mode = False
                console.print("[green]已切换到完整模式（多代理协作）[/]")

            else:
                # 执行研究
                run_research(user_input, simple_mode=simple_mode)

        except KeyboardInterrupt:
            console.print("\n[yellow]操作已取消[/]")
            continue

        except Exception as e:
            logger.error(f"交互错误: {e}")
            console.print(f"[red]发生错误: {e}[/]")


def single_query_mode(query: str, simple: bool = False):
    """
    单次查询模式

    Args:
        query: 研究查询
        simple: 是否使用简单模式
    """
    print_banner()
    run_research(query, simple_mode=simple)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="X-DeepAgents - 智能市场研究报告生成系统"
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="研究查询（可选，不提供则进入交互模式）"
    )
    parser.add_argument(
        "-s", "--simple",
        action="store_true",
        help="使用简单模式（单代理）"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细输出"
    )

    args = parser.parse_args()

    # 设置日志级别
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)

    # 检查 API 配置（openai 当前不支持）
    supported_api_keys = [
        "DEEPSEEK_API_KEY",
        "KIMI_API_KEY",
        "GLM_API_KEY",
        "ALIYUN_API_KEY",
        "DOUBAO_API_KEY",
    ]
    if not any(os.environ.get(k) for k in supported_api_keys):
        console.print("[yellow]警告: 未检测到 API 密钥配置[/]")
        console.print(
            "[dim]请确保 .env 文件中至少配置一个：DEEPSEEK_API_KEY / KIMI_API_KEY / GLM_API_KEY / "
            "ALIYUN_API_KEY / DOUBAO_API_KEY[/]\n"
        )

    # 根据参数选择模式
    if args.query:
        single_query_mode(args.query, simple=args.simple)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
