from app.core.constants import *
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from app.core.state import AgentState
from app.schemas.models import AnalyzerResult
import re
from app.tools.gaodeMCP_tools import create_amap_client



def extract_poi_id(amap_result: str) -> str:
    """从高德 API 返回的字符串中，安全地提取第一个 POI ID"""
    # 高德的 POI ID 通常是 B0 开头的 10 位字母数字组合，如 B001786UY2
    match = re.search(r"['\"]id['\"]:\s*['\"](B0[A-Z0-9]{8})['\"]", str(amap_result))
    if match:
        return match.group(1)
    return ""

analyzer_llm = ChatOpenAI(
    model=MODEL_NAME,
    temperature=float(TEMPERATURE),
    extra_body={"enable_thinking": ENABLE_THINKING},
    max_tokens=int(MAX_TOKENS),
    timeout=float(REQUEST_TIMEOUT),
    max_retries=int(MAX_RETRIES)
)
ANALYZER_PROMPT = app_config["analyzer"]["system_prompt"]


async def analyzer_node(state: AgentState) -> dict:
    client, raw_tools = await create_amap_client()
    tools_dict = {}
    for tool in raw_tools:
        tools_dict[tool.name] = tool
    text_search_tool = tools_dict.get("maps_text_search")

    current_ask_count = state.get("analyzer_count", 0)
    print("🤖 [Analyzer] 正在分析信息完整度与加载长期记忆是否满足指定出行计划所信息...")
    # 获取用户画像
    user_profile = state.get("user_profile", {})
    memory_summary = state.get("memory_summary", "")
    prompt = ChatPromptTemplate.from_messages([
        ("system", ANALYZER_PROMPT),
        ("placeholder", "{messages}")
    ])
    analyzer_llm_structured = analyzer_llm.with_structured_output(AnalyzerResult)
    chain = prompt | analyzer_llm_structured

    # 在调用大模型前，过滤掉非标准对话消息
    clean_messages = [
        m for m in state["messages"]
        if isinstance(m, (HumanMessage, AIMessage, SystemMessage, ToolMessage))
    ]

    response: AnalyzerResult = chain.invoke({
        "messages": clean_messages,
        "user_profile": user_profile,
        "memory_summary": memory_summary
    })

    if not text_search_tool:
        print("  [Analyzer] ⚠️ 未找到搜索工具，跳过 ID 增强。")
        return {"extracted_info": response}
    departure_PoiId = ""
    if response.departure and response.departure not in ["无", "未知", "","null"]:
        print(f"  [Analyzer] 🔍 正在为出发地 '{response.departure}' 检索 POI ID...")
        try:
            # 直接调用工具的异步方法
            search_res = await text_search_tool.ainvoke({"keywords": response.departure})
            poi_id = extract_poi_id(search_res)

            if poi_id:
                # 把 ID 拼接到原来的字符串后面
                departure_PoiId=poi_id
                print(f"  [Analyzer] ✅ 出发地 ID 注入成功: {response.departure},{departure_PoiId}")
            else:
                print(f"  [Analyzer] ⚠️ 无法找到 '{response.departure}' 的精准 ID。")
        except Exception as e:
            print(f"  [Analyzer] ⚠️ 出发地搜索超时或报错: {e}")


    print(response)
    if response.is_complete:
        print("✅ [Analyzer] 核心信息收集完毕，可以将需求交给 Planner 开始排行程了！")
        return {
            "departure": response.departure,
            "destination": response.destination,
            "departure_PoiId": departure_PoiId,
            "time": response.extracted_time,
            "Other_requirements": response.extract_requirements,
            "is_info_complete": True
        }
    else:
        print(f"⚠️ [Analyzer] 信息缺失 发起第 {current_ask_count + 1} 次追问...")
        # 将追问作为系统回复追加到对话中
        return {
            "messages": [AIMessage(content=response.suggested_question)],
            "departure": response.departure,
            "departure_PoiId": departure_PoiId,
            "destination": response.destination,
            "time": response.extracted_time,
            "Other_requirements": response.extract_requirements,
            "is_info_complete": False,
            "analyzer_count": current_ask_count + 1
        }
