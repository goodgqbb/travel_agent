import asyncio
from typing import List, Union
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from app.core.constants import *



class BaseAgent:
    def __init__(self,
                 tools: list,  # 将 tools 作为参数强制传入
                 state_modifier: str = "你是一个全能的AI助手",
                 response_format=None,
                 prompt_js=None):  # 改为 state_modifier
        self.llm = ChatOpenAI(
            model=MODEL_NAME,
            temperature=float(TEMPERATURE),
            extra_body={"enable_thinking": ENABLE_THINKING},
            max_tokens=int(MAX_TOKENS),
            timeout=float(REQUEST_TIMEOUT),
            max_retries=int(MAX_RETRIES)
        )
        system_message = SystemMessage(content=state_modifier)
        # 2. 创建底层的 React Agent

        self.agent_executor = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_message,
        )
        self.output_parser = self.llm.with_structured_output(response_format)
        self.prompt_js = prompt_js

    # 提供一个快捷的调用接口，对外隐藏 LangGraph 的复杂配置
    async def ainvoke(self, input_data: Union[str, List[BaseMessage]], thread_id: str):
        config = {"configurable": {"thread_id": thread_id},}
                  # "recursion_limit": 20}
        print(f"    [BaseAgent] 🚀 正在向 Qwen 发起请求... (Thread: {thread_id})")  # 👈 加这里
        # 1. 如果传入的是完整历史记录（例如从 Planner 的 state["messages"] 传过来）
        print("当前数据：", input_data)
        if isinstance(input_data, list):
            response = await asyncio.wait_for(
                self.agent_executor.ainvoke({"messages": input_data},config=config),
                timeout=float(REQUEST_TIMEOUT)
        )
        # 2. 如果传入的是单句字符串（例如你以前的单点测试代码）
        elif isinstance(input_data, str):
            response = await asyncio.wait_for(
                self.agent_executor.ainvoke({"messages": [("user", input_data)]},config=config),
                timeout=float(REQUEST_TIMEOUT)
            )
        else:
            raise ValueError("BaseAgent.ainvoke 仅支持传入 str 或 List[BaseMessage] 类型")
        # 返回最后一条大模型的回复文本
        print("    [BaseAgent] ✅ Qwen 返回了结果！")  # 👈 加这里
        raw_content = response["messages"][-1].content
        # print("原始信息", raw_content)
        # 💡 新增：把用户最初始的输入信息提取出来
        original_context = ""
        if isinstance(input_data, list):
            # 将历史对话拼接成字符串，作为背景板透传
            original_context = "\n".join([f"{msg.type}: {msg.content}" for msg in input_data if msg.content])
        else:
            original_context = input_data

        # 💡 修改：在 Prompt 中明确告诫排版员，必须参考原始上下文，禁止脑补
        parser_prompt = f"""
            请将以下内容整理成指定的 JSON 格式。
            【极其重要的纪律】：
            你必须严格参考下方的[原始对话上下文]来补全JSON，特别是出发地、时间等约束条件！
            如果[已知内容]和[原始对话上下文]中都没有提到的细节（如机场、高铁站），填“无”或保留为空，绝对禁止自行捏造！
            [原始对话上下文]：
            {original_context}
            [已知内容]（草稿）：
            {raw_content}
            JSON格式示例:{self.prompt_js}
            """
        structured_res = await self.output_parser.ainvoke(parser_prompt)
        # print("转换后的内容：", structured_res)
        return structured_res
