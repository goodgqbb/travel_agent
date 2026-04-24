from langgraph.graph import StateGraph, START, END
from app.agents.STM_Agent import recursive_memory_node
from app.core.state import AgentState
from app.agents.analyzer import analyzer_node
from app.memory.redis_saver import get_redis_saver
from app.core.planner_graph import planner_app


def route_from_analyzer(state: AgentState):
    if state.get("is_info_complete"):
        return "planner"
    else:
        ask_count = state.get("analyzer_count", 0)
        if ask_count >= 3:
            print("🚨 [Router] 追问次数已达 3 次上限！强制进入 Planner！")
            return "planner"
        else:
            return "end"


# ==========================================
# 主流程图编排
# ==========================================
workflow = StateGraph(AgentState)

# 添加外层节点
workflow.add_node("analyzer", analyzer_node)

# ✨ 核心魔法：直接把编译好的子图 planner_app 当作节点加进来
workflow.add_node("planner", planner_app)

workflow.add_node("memory", recursive_memory_node)
# 连接边
workflow.add_edge(START, "analyzer")
workflow.add_conditional_edges(
    "analyzer",
    route_from_analyzer,
    {
        "planner": "planner",
        "end": END
    }
)
workflow.add_edge("planner", "memory")
workflow.add_edge("memory", END)

memory = get_redis_saver()
main_app = workflow.compile(checkpointer=memory)
