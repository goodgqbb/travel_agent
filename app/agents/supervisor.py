from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from app.schemas.models import RouteDecision
from app.tools.get_time_tools import get_current_time
from app.core.constants import *


SUPERVISORAGENT_PROMPT = app_config["supervisor"]["system_prompt"]


class SupervisorAgent:
    def __init__(self):
        # Supervisor 不需要工具，只需要最聪明的模型来进行逻辑判断
        self.llm = ChatOpenAI(
            model=MODEL_NAME,
            temperature=float(TEMPERATURE),
            extra_body={"enable_thinking": ENABLE_THINKING},
            max_tokens=int(MAX_TOKENS),
            timeout=float(REQUEST_TIMEOUT),
            max_retries=int(MAX_RETRIES)

        )
        self.llm.bind_tools([get_current_time])
        # 强制模型输出符合 RouteDecision 结构的字典/对象
        self.structured_llm = self.llm.with_structured_output(RouteDecision)
        self.system_prompt = SystemMessage(content=SUPERVISORAGENT_PROMPT)

    async def ainvoke(self, messages: list):
        """
        传入当前的对话历史，返回结构化的路由决策
        """
        # 将系统提示词与历史消息合并后发给大模型
        prompt_messages = [self.system_prompt] + list(messages)

        decision = await self.structured_llm.ainvoke(prompt_messages)
        return decision
