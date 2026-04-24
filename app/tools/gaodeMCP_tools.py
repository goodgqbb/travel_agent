import os
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

# 加载环境变量
load_dotenv()
AMAP_API_KEY = os.getenv("AMAP_API_KEY")


# 高德mcp客户端
async def create_amap_client():
    # 连接高德 MCP（SSE 或 stdio 二选一）
    client = MultiServerMCPClient({
        "amap-amap-sse": {
            "url": f"https://mcp.amap.com/sse?key={AMAP_API_KEY}",
            "transport": "sse"
        }
    })
    tools = await client.get_tools()
    return client, tools
