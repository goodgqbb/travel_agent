from typing import List
import tiktoken
from langchain_core.messages import RemoveMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from app.core.state import AgentState
from app.core.constants import *



def get_token_count(messages: List[BaseMessage]) -> int:
    """
    估算消息的 Token 数量。
    如果你使用的是兼容 OpenAI 的本地模型，可以直接用 tiktoken 的 cl100k_base 作为基准估算。
    """
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        num_tokens = 0
        for message in messages:
            num_tokens += len(encoding.encode(message.content))
        return num_tokens
    except Exception:
        # Fallback 粗略估算：中文字符较多时，约 1 个字符 1.5 个 Token
        return sum(len(m.content) * 1.5 for m in messages)


async def recursive_memory_node(state: AgentState) -> dict:
    messages = state["messages"]
    current_summary = state.get("memory_summary", "")
    # 1. 检查是否触发压缩阈值
    token_count = get_token_count(messages)
    if token_count <= 4000:
        # 未达到阈值，不修改 state
        return {}
    # 2. 动态寻找对话轮次的切分点
    human_msg_indices = [
        i for i, msg in enumerate(messages)
        if isinstance(msg, HumanMessage) or msg.type == "human"
    ]
    KEEP_TURNS = 1
    if len(human_msg_indices) <= KEEP_TURNS:
        return {}
    split_index = human_msg_indices[-KEEP_TURNS]
    messages_to_compress = messages[:split_index]

    # 3. 准备调用小模型
    llm = ChatOpenAI(
        model=MODEL_NAME,
        temperature=float(TEMPERATURE),
        extra_body={"enable_thinking": ENABLE_THINKING},
        max_tokens=int(MAX_TOKENS),
        timeout=float(REQUEST_TIMEOUT),
        max_retries=int(MAX_RETRIES)

    )
    # 4. 构建压缩 Prompt
    conversation_str = ""
    for m in messages_to_compress:
        role = "User" if (isinstance(m, HumanMessage) or m.type == "human") else "AI Expert"
        content = m.content if isinstance(m.content, str) else str(m.content)

        # 【修改点1】放宽截断限制，防止将末尾的 poi_id 意外切掉
        if len(content) > 1500:
            content = content[:1500] + "...(内容已截断)"
        conversation_str += f"{role}: {content}\n"
    # 【修改点2】在 Prompt 中以最高优先级强调保留 poi_id
    summary_prompt = (
        "你是一个专业且严谨的系统记忆整理助手。请结合【已有记忆摘要】和【新增的早期对话历史】，"
        "生成一段更新后的、凝练的记忆摘要。\n\n"
        "【核心要求】：\n"
        "1. 记录用户的行程偏好（如出发地点、目的地、对住宿/饮食的要求、时间安排）。\n"
        "2. **极其重要：必须完整保留所有确定的地点（出发地点、景点、酒店、餐厅等）及其对应的 `poi_id` 信息，格式要求如：成都金融城双子塔(poi_id: B0J6RAP5S2)。绝对不可遗漏！**\n"
        "3. 忽略多余的寒暄和与核心行程规划无关的废话。\n\n"
        f"【已有记忆摘要】:\n{current_summary if current_summary else '暂无'}\n\n"
        f"【新增的早期对话历史】:\n{conversation_str}\n\n"
        "请直接输出新的摘要，确保包含所有的 poi_id，不要包含任何客套话："
    )
    print("执行压缩：", conversation_str)
    # 5. 调用 LLM 生成新摘要
    response = await llm.ainvoke([HumanMessage(content=summary_prompt)])
    new_summary = response.content
    print("压缩后的信息：", new_summary)
    # 6. 生成删除指令
    delete_instructions = [RemoveMessage(id=m.id) for m in messages_to_compress if hasattr(m, 'id') and m.id]
    # 7. 更新状态
    return {
        "memory_summary": new_summary,
        "messages": delete_instructions
    }
