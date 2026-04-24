from datetime import datetime
from langchain_core.tools import tool

from app.memory.mysql_meta import get_messages_by_session


@tool
def get_current_time() -> str:
    """
    获取当前的精确时间、日期以及星期几。
    当需要了解‘今天’、‘现在’或规划具体日期行程时，应调用此工具。
    """
    # 获取当前系统时间
    now = datetime.now()

    # 定义星期几的中文映射
    week_days = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday_str = week_days[now.weekday()]

    # 格式化输出：2024-05-20 14:30:05 星期一
    current_time_info = now.strftime("%Y-%m-%d %H:%M:%S") + f" {weekday_str}"

    return f"当前的系统时间是：{current_time_info}"


@tool
def retrieve_past_memory(session_id: str, keyword: str) -> str:
    """
    【记忆检索工具】
    当你想不起过去规划的细节（如：之前定了哪个酒店？用户之前提到的备选景点是什么？）时调用此工具。
    输入 session_id 和 搜索关键词，将返回相关的历史原始对话。
    """
    # 这里写一个简单的文本过滤，如果有向量库更好
    db_messages = get_messages_by_session(session_id)
    results = [msg["content"] for msg in db_messages if keyword in msg["content"]]

    if results:
        return "检索到的历史细节：" + "\n".join(results[:3])  # 只返回最相关的几条
    return "记忆中未找到相关细节。"






