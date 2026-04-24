from typing import TypedDict, Annotated, List, Dict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # 1.短期记忆 (Session 会话)
    messages: Annotated[List[BaseMessage], add_messages]
    # 2.长期记忆 (用户画像+喜好)
    user_profile: Dict[str, Any]
    # 3. 意图与需求
    departure: str  # 出发地点
    departure_PoiId: str
    destination: str  # 目的地点
    time: str  # 游玩时间
    Other_requirements: str
    # 4. 计划与外部数据
    current_plan: List[Dict[str, str]]
    env_data: Dict[str, Any]
    # 5. 校验与工程兜底
    replan_count: int
    # 6.需求模块：
    is_info_complete: bool
    analyzer_count: int
    # 7.用于 Planner 内部 Supervisor 的路由控制
    next_node: str
    # 8.短期记忆摘要
    memory_summary: str
