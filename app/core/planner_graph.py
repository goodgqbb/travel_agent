import asyncio
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, ToolMessage
from app.agents.supervisor import SupervisorAgent
from app.core.state import AgentState
from app.agents.SubAgent import AttractionAgent, WeatherAgent, HotelAgent, ItineraryAgent
from app.tools.gaodeMCP_tools import create_amap_client
from app.tools.get_time_tools import get_current_time
from app.core.config import app_config

supervisor_agent = SupervisorAgent()
# 声明全局变量，用于懒加载存储打工人 Agent 实例
_weather_agent = None
_attraction_agent = None
_hotel_agent = None
_itinerary_agent = None
_amap_lock = None


def rate_limit_wrapper(tool: StructuredTool) -> StructuredTool:
    """给工具套上一层强制排队+延时的外壳"""
    original_coro = tool.coroutine

    async def throttled_coro(*args, **kwargs):
        # 强制获取锁，如果别人在请求，这里就会排队等待
        async with _amap_lock:
            # 拿到锁之后，强制休眠 0.5 秒（高德免费版 QPS 极低，0.5秒能稳稳绕过限制）
            await asyncio.sleep(0.1)
            # 执行真正的网络请求
            return await original_coro(*args, **kwargs)

    # 重新组装并返回受控的新工具
    return StructuredTool(
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema,
        func=tool.func,
        coroutine=throttled_coro
    )


async def get_or_create_agents():
    """
    单例模式/懒加载：确保只在图的执行期（事件循环内）初始化一次异步工具和 Agent
    """
    global _weather_agent, _attraction_agent, _hotel_agent, _itinerary_agent, _amap_lock
    if _amap_lock is None:
        _amap_lock = asyncio.Lock()
    if _weather_agent is None:
        print("  [Init] 🔄 正在初始化异步地图工具与打工人 Agents...")
        print("  [Init] 📡 正在尝试连接高德 MCP 工具...")
        client, raw_tools = await create_amap_client()
        # 1. 构建工具池字典 (Tool Pool)
        tools_dict = {}
        for tool in raw_tools:
            # 给高德 API 套上限流锁，并以 tool.name 作为 key 存入字典
            tools_dict[tool.name] = rate_limit_wrapper(tool)
        # 获取本地时间工具的名称（兼容 getattr 避免报错），并直接存入字典，无需限流
        tools_dict["get_current_time"] = get_current_time
        print(f"  [Init] ✅ 高德 MCP 连接成功！共加载入库 {len(tools_dict)} 个工具")
        # 2. 为四大专家精准划定工具权限清单 (RBAC)

        weather_tools_list = app_config["agents"]["weather"]["tools"]
        attraction_tools_list = app_config["agents"]["attraction"]["tools"]
        hotel_tools_list = app_config["agents"]["hotel"]["tools"]
        itinerary_tools_list = app_config["agents"]["itinerary"]["tools"]

        # 闭包辅助函数：根据清单去工具池里拿真家伙
        def assign_tools(tool_names_list):
            assigned = []
            for name in tool_names_list:
                if name in tools_dict:
                    assigned.append(tools_dict[name])
                else:
                    print(f"  [Warning] ⚠️ 未找到工具 '{name}'，已跳过分配。")
            return assigned

        # 3. 实例化 Agent，注入它们各自的专属工具包
        _weather_agent = WeatherAgent(tools=assign_tools(weather_tools_list),
                                      system_prompt=app_config["agents"]["weather"]["system_prompt"],
                                      prompt_example=app_config["agents"]["weather"]["prompt_example"], )
        _attraction_agent = AttractionAgent(tools=assign_tools(attraction_tools_list),
                                            system_prompt=app_config["agents"]["attraction"]["system_prompt"],
                                            prompt_example=app_config["agents"]["attraction"]["prompt_example"])
        _hotel_agent = HotelAgent(tools=assign_tools(hotel_tools_list),
                                  system_prompt=app_config["agents"]["hotel"]["system_prompt"],
                                  prompt_example=app_config["agents"]["hotel"]["prompt_example"])
        _itinerary_agent = ItineraryAgent(tools=assign_tools(itinerary_tools_list),
                                          system_prompt=app_config["agents"]["itinerary"]["system_prompt"],
                                          prompt_example=app_config["agents"]["itinerary"]["prompt_example"])
        print("  [Init] 🎯 专家 Agent 专属工具分配完毕！")
    return _weather_agent, _attraction_agent, _hotel_agent, _itinerary_agent


# 2. 包装节点函数
async def supervisor_node(state: AgentState):
    """总控节点：读取 Analyzer 提取的需求，并进行路由或总结"""
    raw_messages = state.get("messages", [])
    clean_messages = [
        m for m in raw_messages
        if isinstance(m, (HumanMessage, AIMessage, SystemMessage, ToolMessage))
    ]
    print("supervisor_node的clean_messages", clean_messages)
    memory_summary = state.get("memory_summary", "无")
    departure = state.get("departure", "")
    departure_PoiId = state.get("departure_PoiId", "")
    destination = state.get("destination", "")
    time = state.get("time", "")
    Other_requirements = state.get("Other_requirements", "")

    context_prompt = f"""
    【前置分析信息】：
    "历史消息": {memory_summary}
    出发地点: {departure}
    出发地点PoiId: {departure_PoiId}
    目的地点: {destination}
    时间: {time}
    其他要求: {Other_requirements}
    请根据以上信息协调你的下属专家。如果用户有新的反馈，请针对反馈路由给对应专家。
    """
    # 将背景信息插入到 Supervisor 的判断逻辑中
    decision = await supervisor_agent.ainvoke([SystemMessage(content=context_prompt)] + list(clean_messages))
    print(f"\n🧠 [Supervisor] 分析完毕！决定下一步路由给: {decision.next_node}")
    if decision.next_node == "FINISH":
        return {"messages": [AIMessage(content=decision.reply_to_user)], "next_node": "FINISH"}
    else:
        return {"next_node": decision.next_node}


async def weather_node(state: AgentState, config: RunnableConfig):
    print("  [Planner内部] -> ⛅ WeatherAgent 执行中...")
    weather_ag, _, _, _ = await get_or_create_agents()

    # 从 config 中提取当前对话的 thread_id，默认为 default
    thread_id = config.get("configurable", {}).get("thread_id", "default_thread")
    memory_summary = state.get("memory_summary", "无")
    departure = state.get("departure", "")
    departure_PoiId = state.get("departure_PoiId", "")
    destination = state.get("destination", "")
    time = state.get("time", "")
    Other_requirements = state.get("Other_requirements", "")

    context_msg = SystemMessage(
        content=f"【后台补充信息】历史消息记录：{memory_summary} 用户出发地：{departure}，出发地点PoiId: {departure_PoiId} 用户目的地：{destination}\
        时间：{time}。用户要求：{Other_requirements}")
    messages_to_send = [context_msg] + list(state["messages"])
    reply = await weather_ag.ainvoke(messages_to_send, thread_id)
    print(f"  🎡 [weather_node] 汇报工作: {reply}...")

    return {"messages": [AIMessage(content=f"【天气专家】: {reply}")]}


async def attraction_node(state: AgentState, config: RunnableConfig):
    print("  [Planner内部] -> 🎡 AttractionAgent 执行中...")
    _, attraction_ag, _, _ = await get_or_create_agents()

    thread_id = config.get("configurable", {}).get("thread_id", "default_thread")

    memory_summary = state.get("memory_summary", "无")
    departure = state.get("departure", "")
    departure_PoiId = state.get("departure_PoiId", "")
    destination = state.get("destination", "")
    time = state.get("time", "")
    Other_requirements = state.get("Other_requirements", "")

    context_msg = SystemMessage(
        content=f"【后台补充信息】历史消息记录：{memory_summary} 用户出发地：{departure}，出发地点PoiId: {departure_PoiId} 用户目的地：{destination}\
            时间：{time}。用户要求：{Other_requirements}")
    messages_to_send = [context_msg] + list(state["messages"])
    reply = await attraction_ag.ainvoke(messages_to_send, thread_id)
    print(f"  🎡 [attraction_node] 汇报工作: {reply}...")
    return {"messages": [AIMessage(content=f"【景点专家】: {reply}")]}


async def hotel_node(state: AgentState, config: RunnableConfig):
    print("  [Planner内部] -> 🏨 HotelAgent 执行中...")
    _, _, hotel_ag, _ = await get_or_create_agents()

    thread_id = config.get("configurable", {}).get("thread_id", "default_thread")

    memory_summary = state.get("memory_summary", "无")
    departure = state.get("departure", "")
    departure_PoiId = state.get("departure_PoiId", "")
    destination = state.get("destination", "")
    time = state.get("time", "")
    Other_requirements = state.get("Other_requirements", "")

    context_msg = SystemMessage(
        content=f"【后台补充信息】历史消息记录：{memory_summary} 用户出发地：{departure}，出发地点PoiId: {departure_PoiId} 用户目的地：{destination}\
            时间：{time}。用户要求：{Other_requirements}")
    messages_to_send = [context_msg] + list(state["messages"])
    reply = await hotel_ag.ainvoke(messages_to_send, thread_id)
    print(f"  🎡 [hotel_node] 汇报工作: {reply}...")

    return {"messages": [AIMessage(content=f"【酒店专家】: {reply}")]}


async def itinerary_node(state: AgentState, config: RunnableConfig):
    print("  [Planner内部] -> ⛅ ItineraryAgent 执行中...")
    _, _, _, itinerary_ag = await get_or_create_agents()

    # 从 config 中提取当前对话的 thread_id，默认为 default
    thread_id = config.get("configurable", {}).get("thread_id", "default_thread")

    memory_summary = state.get("memory_summary", "无")
    departure = state.get("departure", "")
    departure_PoiId = state.get("departure_PoiId", "")
    destination = state.get("destination", "")
    time = state.get("time", "")
    Other_requirements = state.get("Other_requirements", "")

    context_msg = SystemMessage(
        content=f"【后台补充信息】历史消息记录：{memory_summary} 用户出发地：{departure}，出发地点PoiId: {departure_PoiId} 用户目的地：{destination}\
            时间：{time}。用户要求：{Other_requirements}")
    messages_to_send = [context_msg] + list(state["messages"])
    reply = await itinerary_ag.ainvoke(messages_to_send, thread_id)
    print(f"  🎡 [itinerary_node] 汇报工作: {reply}...")

    return {"messages": [AIMessage(content=f"【行程专家】: {reply}")]}


# 3. 编排 Planner 子图
planner_workflow = StateGraph(AgentState)

planner_workflow.add_node("Supervisor", supervisor_node)
planner_workflow.add_node("WeatherAgent", weather_node)
planner_workflow.add_node("AttractionAgent", attraction_node)
planner_workflow.add_node("HotelAgent", hotel_node)
planner_workflow.add_node("ItineraryAgent", itinerary_node)
# Supervisor 路由逻辑
planner_workflow.add_edge(START, "Supervisor")
planner_workflow.add_conditional_edges(
    "Supervisor",
    lambda state: state["next_node"],
    {
        "WeatherAgent": "WeatherAgent",
        "AttractionAgent": "AttractionAgent",
        "HotelAgent": "HotelAgent",
        "ItineraryAgent": "ItineraryAgent",
        "FINISH": END
    }
)
for node in ["WeatherAgent", "AttractionAgent", "HotelAgent", "ItineraryAgent"]:
    planner_workflow.add_edge(node, "Supervisor")
planner_app = planner_workflow.compile()
