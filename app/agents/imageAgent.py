import base64
from app.core.constants import *
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from app.schemas.models import Multi_Result
from langchain_core.output_parsers import PydanticOutputParser  # 新增导入


parser = PydanticOutputParser(pydantic_object=Multi_Result)

analyzer_llm = ChatOpenAI(
    model=MODEL_NAME,
    temperature=float(TEMPERATURE),
    extra_body={"enable_thinking": ENABLE_THINKING},
    max_tokens=int(MAX_TOKENS),
    timeout=float(REQUEST_TIMEOUT),
    max_retries=int(MAX_RETRIES)
)

ANALYZER_PROMPT = f"""
分析这张图片或视频。识别以下特征：1. 具体的景点名称或地理标志（如果可见）；
2. 环境氛围（例如：户外自然、热闹市集、安静博物馆、亲子友好）；
3. 关键的限制条件（例如：宠物是否可以进入、是否需要长时间徒步）。
【输出格式要求】
{parser.get_format_instructions()}
"""


# 4. 图片编码辅助函数
def encode_image(image_path: str) -> str:
    """将本地图片转为 Base64 编码"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


async def analyze_travel_image(image_path: str) -> Multi_Result:
    """处理用户上传的图片并返回结构化数据"""

    # 获取图片的 Base64 编码
    base64_image = encode_image(image_path)
    # 组合 Prompt (结合业务需求 + JSON 格式要求)

    # 构造 LangChain 的多模态消息
    message = HumanMessage(
        content=[
            {"type": "text", "text": ANALYZER_PROMPT},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                },
            },
        ]
    )
    print("正在调用 VLM 分析图片，请稍候...")
    # 执行调用
    response = await analyzer_llm.ainvoke([message])
    result: Multi_Result = parser.invoke(response)
    return result


if __name__ == "__main__":
    test_image_path = r"D:\Study\pycharmpro\weekend_planner_agent\testimage\1.png"  # 替换为你的本地图片路径

    if os.path.exists(test_image_path):
        try:
            result = analyze_travel_image(test_image_path)
            print("\n=== 视觉感知层输出 (JSON) ===")
        except Exception as e:
            print(f"处理失败: {e}")
    else:
        print(f"请先在代码同级目录准备一张名为 '{test_image_path}' 的图片。")
