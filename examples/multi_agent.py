import asyncio

from deepagents import CompiledSubAgent, create_deep_agent
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from deep_agents.llm.my_llm import llm

gaode_mcp_server_config = {
    "url": "https://mcp.amap.com/mcp?key=01467c30e6e6d2cca314e3b657de3fbd",
    "transport": "streamable_http",
}

my12306_mcp_server_config = {
    "url": "https://mcp.api-inference.modelscope.net/ac70b4fdd64a40/mcp",
    "transport": "streamable_http",
}

analysis_mcp_server_config = {
    "url": "https://mcp.api-inference.modelscope.net/312fc85d97954a/sse",
    "transport": "sse",
}


# 开发多步骤的，多子智能体的负责的一个Agent项目
# 路线规划，火车票查询，数据分析、爬取网页等各种能力的agent

system_prompt = """
# 角色与核心目标
你是主协调智能体，负责高效处理用户请求。你的首要任务是分析用户问题，若其属于预设的专门领域，则分配给相应的子智能体处理；否则，由你亲自解答。

# 任务分配规则
请严格依据以下关键词和领域描述，决定是否进行任务分配：

## 高德地图子智能体负责领域
- **负责内容**：一切与地理位置、导航、出行规划、周边搜索相关的问题。
- **触发关键词**：天气、地图、位置、导航、路线、路径规划、公交、地铁、驾车、步行、附近、周边、搜索地点、POI、经纬度、路况、拥堵、距离、里程。

## 12306铁路查询子智能体负责领域
- **负责内容**：一切与中国铁路客运相关的问题，特别是车票查询和预订。
- **触发关键词**：火车、高铁、动车、车次、车票、票价、余票、时刻表、火车站、车站、12306、订票、购票、抢票、列车、站台、正晚点、检票口。

# 工作流程
1.  **分析请求**：仔细阅读用户问题，识别其中的核心意图和关键词。
2.  **匹配领域**：将识别出的关键词与上述“负责领域”进行匹配。
    -   如果问题**明确且主要**属于某一个子领域（例如，问题中同时包含“北京”和“天气”），则毫不犹豫地将任务分配给对应的子智能体。
    -   如果问题**同时涉及**两个子领域（例如，“帮我查一下去上海的火车票，并规划一下从家到火车站的地铁路线”），这是一个需要协调的复杂任务。当前版本请你直接处理，向用户说明这是一个复杂请求，并尝试分步骤给出建议或优先处理其中一个最明确的需求。
    -   如果问题**不属于**上述任何子领域，则由你亲自回答。
3.  **执行与响应**：一旦做出分配决定，即调用相应的子智能体，并将其回复完整地呈现给用户。若是你亲自回答，请确保回应清晰、准确、有帮助。

# 通用行为规范
- 你的回答应保持专业、友好和乐于助人的态度。
- 如果无法确定用户意图，或问题模糊，应主动询问澄清。
- 对于超出你知识范围或工具能力的问题，如实告知，不要编造信息。
"""

mcp_client = MultiServerMCPClient(
    {
        "gaode": gaode_mcp_server_config,
        "12306": my12306_mcp_server_config,
        "fenxi": analysis_mcp_server_config,
    }
)

async def create_my_agent():
    gaode_tools = await mcp_client.get_tools(server_name="gaode")
    railway_tools = await mcp_client.get_tools(server_name="12306")
    await mcp_client.get_tools(server_name="fenxi")

    print(f"所有高德地图工具：{gaode_tools}")
    print(f"所有高德地图工具的数量：{len(gaode_tools)}")

    gaode_assistant = create_agent(
        model=llm,
        tools=gaode_tools,
        system_prompt="您是一位高德地图的子Agent，负责查询天气、地图信息和规划行程路线。",
    )

    gaode_subagent = CompiledSubAgent(
        name="gaode_assistant",
        description="专门处理查询天气、地图信息和规划行程路线的智能体",
        runnable=gaode_assistant,
    )

    railway_assistant = create_agent(
        model=llm,
        tools=railway_tools,
        system_prompt="您是一位12306铁路查询的子Agent，负责查询火车站、高铁站的信息和查询各种火车、高铁票。",
    )

    railway_subagent = CompiledSubAgent(
        name="railway_assistant",
        description="专门查询火车站、高铁站的信息和查询各种火车、高铁票的智能体",
        runnable=railway_assistant,
    )

    subagents = [gaode_subagent, railway_subagent]

    return create_deep_agent(model=llm, subagents=subagents, system_prompt=system_prompt)


deep_agent = asyncio.run(create_my_agent())
