import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from dotenv import load_dotenv
from app.agents.SubAgent import AttractionAgent, WeatherAgent, HotelAgent
from app.tools.gaodeMCP_tools import create_amap_client
# 加载环境变量
load_dotenv()
AMAP_API_KEY = os.getenv("AMAP_API_KEY")


async def main():
    client, all_amap_tools = await create_amap_client()
    attraction_agent = AttractionAgent(tools=all_amap_tools)
    weather_agent = WeatherAgent(tools=all_amap_tools)
    hotel_agent = HotelAgent(tools=all_amap_tools)

    thread_id = "user_123_weekend_plan"

    print("=== 开始并行或按顺序调用不同的专家 ===")

    weather_reply = await weather_agent.ainvoke("这周末重庆南岸区天气怎么样？", thread_id)
    print(f"🌤 天气助手: {weather_reply}\n")

    attr_reply = await attraction_agent.ainvoke("根据这个天气，南岸区有什么好玩的景点推荐？", thread_id)
    print(f"🎡 景点助手: {attr_reply}\n")

    hotel_reply = await hotel_agent.ainvoke("我想在这附近找一家人均300左右的酒店，带停车场的", thread_id)
    print(f"🏨 酒店助手: {hotel_reply}\n")


if __name__ == "__main__":
    asyncio.run(main())
