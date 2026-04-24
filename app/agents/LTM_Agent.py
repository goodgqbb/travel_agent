from pathlib import Path
import json
from langchain_openai import ChatOpenAI
from app.memory.mysql_meta import mark_session_extracted
from app.core.constants import *



class JsonLTMManager:
    def __init__(self, base_path="./app/data"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_path(self):
        return self.base_path / "user_profile.json"

    def load_profile(self):
        """读取长期记忆"""
        path = self._get_path()
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_profile(self, profile_data):
        """保存长期记忆"""
        path = self._get_path()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)


async def consolidate_session_to_ltm(session_id: str, ltm_json: JsonLTMManager, session_msg: str):
    """
    后台任务：将上一个会话的短期摘要，提炼成长期画像
    """
    print(f"🕵️‍♂️ [LTM 盘点] 开始提炼历史会话 ({session_id}) 的长期记忆...")
    old_profile = ltm_json.load_profile()
    extractor_prompt = f"""
    你是一个专业的用户画像提炼师。
    以下是用户上一次旅行规划的【完整对话】：
    "{session_msg}"
    已知用户的【现有长期画像】为：
    {json.dumps(old_profile, ensure_ascii=False)}
    【任务】：
    从行程信息中，剥离出单次旅行的特定信息（如“去某个具体城市”、“住某家特定酒店”），**仅通过分析用户输入，提取出用户可能在未来旅行中继续保持的长期偏好**
    （如：常用出发地点、出行偏好、带娃需求、怕高反、饮食习惯、对住宿品质要求高等）。
    【输出格式要求】：
    请将新发现的偏好与【现有长期画像】合并。
    你必须严格按照以下 JSON 结构输出。如果某个字段在对话中没有体现，请保留为空数组 [] 或空字符串 ""。绝对不要随意捏造信息或增加根节点。
    【JSON 结构示例（仅展示字段含义，请根据实际对话内容提取填充）】：
    {{
      "basic_info": {{
        "home_city": "<字符串：用户的常住地或常用出发城市，若无则留空>",
        "companions": "<字符串：常见的同行人员特征，如情侣、带小孩，若无则留空>"
      }},
      "preferences": {{
        "travel_style": ["<数组：旅行风格偏好，如深度游、打卡游>"],
        "accommodation": "<字符串：对住宿环境的长期要求，如安静、无烟房>",
        "dietary": ["<数组：饮食禁忌或长期偏好，如不吃辣、海鲜过敏>"],
        "transportation": "<字符串：偏好的交通方式，如偏好自驾、拒绝红眼航班>"
      }},
      "health_notes": ["<数组：与出行相关的健康注意事项，如易高反、有鼻炎>"]
    }}
    """
    try:
        llm = ChatOpenAI(
            model=MODEL_NAME,
            temperature=float(TEMPERATURE),
            extra_body={"enable_thinking": ENABLE_THINKING},
            max_tokens=int(MAX_TOKENS),
            timeout=float(REQUEST_TIMEOUT),
            max_retries=int(MAX_RETRIES)

        )
        response = await llm.ainvoke(extractor_prompt)
        raw_content = response.content.strip()
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        elif raw_content.startswith("```"):
            raw_content = raw_content[3:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]
        new_profile = json.loads(raw_content)
        # 存入数据库/JSON
        ltm_json.save_profile(new_profile)

        # 🎯 极其重要：把这个会话标记为“已提取”，避免下次重复提取
        mark_session_extracted(session_id)
        print(f"✨ [LTM 盘点] 会话 ({session_id}) 提取完成！最新长期画像: {new_profile}")

    except Exception as e:
        print(f"⚠️ [LTM 盘点] 提取失败: {e}")
