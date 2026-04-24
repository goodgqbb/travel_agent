import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pprint import pprint
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from app.core.state import AgentState
from app.agents.analyzer import analyzer_node


def route_from_analyzer(state: AgentState):
    """
    决定 Analyzer 执行完后，图应该往哪里走
    """
    if state.get("is_info_complete"):
        return "planner"  # 1. 信息完整，直接进入规划师节点
    else:
        ask_count = state.get("analyzer_count", 0)
        if ask_count >= 3:
            # 2. 熔断机制：已经追问了 3 次还是不全，强制放行！
            print("🚨 [Router] 追问次数已达 3 次上限！触发熔断，强制进入 Planner 盲排行程！")
            return "planner"
        else:
            # 3. 正常追问：中断图的执行，将消息返回给前端（用户），等待用户下一次回复
            return "end"
# ==========================================
# 3. 编排并编译测试图
# ==========================================
workflow = StateGraph(AgentState)

workflow.add_node("analyzer", analyzer_node)

workflow.add_edge(START, "analyzer")
workflow.add_conditional_edges("analyzer",
    route_from_analyzer,
    {
        "planner": "planner",# 如果 route_from_analyzer 返回 "planner"，就走到 planner 节点
        "end": END            # 如果返回 "end"，图就暂停，等真实用户打字
    }
)
workflow.add_edge("planner", END)

app = workflow.compile()

# ==========================================
# 4. 运行测试
# ==========================================
if __name__ == "__main__":
    # 模拟长期记忆调用
    LTM_memory = {
        "home_city": "重庆市南岸区",
        "pet": "有一只3岁的金毛",
        "dietary_restrictions": "不吃香菜，喜欢清淡",
        "driving_preference": "没有车，喜欢地铁出行"
    }

    # 构造用户的初始输入
    initial_state = {
        "messages": [HumanMessage(content="我在重庆市南岸区，这周末我想去爬山，有什么推荐吗")],
        "user_profile": LTM_memory,
        "user_intent": "weekend_planning",
        "core_requirements": {},
        "is_info_complete": False,
        "current_plan": [],
        "env_data": {},
        "critic_feedback": "无，首次规划",
        "replan_count": 0,
        "analyzer_count": 0,
    }

    print("🚀 开始执行 LangGraph 测试...\n")

    # 使用 stream 方法运行，可以看到每个节点的流转
    for output in app.stream(initial_state):
        # output 会输出当前刚刚执行完的节点名称和返回的数据增量
        for node_name, state_update in output.items():
            print(f"\n--- 节点 [{node_name}] 执行完毕 ---")

    print("\n🎉 测试流转结束！最终生成的计划：")
    # 这里需要获取最终的完整状态，在 stream 中不方便直接拿，但可以通过 invoke
    res = app.invoke(initial_state)
    pprint(res)
