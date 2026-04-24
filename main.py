import os
from contextlib import asynccontextmanager
from app.core.config import app_config
import uvicorn
import base64
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.templating import Jinja2Templates
from langchain_core.messages import HumanMessage, AIMessage
from app.agents.LTM_Agent import JsonLTMManager, consolidate_session_to_ltm
from app.agents.imageAgent import analyze_travel_image
from app.core.main_graph import main_app
import langchain
from app.memory.mysql_meta import init_mysql_db, create_session, update_session_title, get_active_sessions, add_message, \
    get_messages_by_session, update_session_summary, get_unextracted_sessions, get_user_message
import uuid
import traceback
from fastapi import BackgroundTasks
# 总结长期记忆
ltm_json = JsonLTMManager()

langchain.debug = app_config["system"]["debug_mode"]  # 👈 开启全局 Debug 模式
# 启动时初始化表
init_mysql_db()

# 工具函数：将上传的文件转为 Base64（用于多模态模型）
async def encode_image(upload_file: UploadFile):
    content = await upload_file.read()
    return base64.b64encode(content).decode('utf-8')


# 👈 2. 新增 FastAPI 生命周期事件：启动时自动建立 Redis 索引
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [系统启动] 正在检查并建立 Redis Checkpoint 索引...")
    # 直接通过 main_app 拿到挂载的 checkpointer 执行初始化
    if hasattr(main_app, "checkpointer") and main_app.checkpointer is not None:
        await main_app.checkpointer.setup()
        print("✅ [系统启动] Redis 索引准备就绪！")
    yield


# 👈 3. 将 lifespan 绑定到 FastAPI 应用中
app = FastAPI(title="Weekend Planner Agent API", lifespan=lifespan)
# 配置 Jinja2 模板目录
templates = Jinja2Templates(directory="templates")


@app.get("/api/sessions")
async def fetch_sessions():
    """供前端左侧边栏调用"""
    sessions = get_active_sessions()
    return {"sessions": sessions}


@app.post("/api/sessions")
async def add_session(background_tasks: BackgroundTasks, ):
    """前端点击 +新建会话 时调用"""
    session_id = uuid.uuid4().hex
    create_session(session_id)

    # 2. 判断之前有没有没有总结过的会话
    unextracted_records = get_unextracted_sessions(session_id)  # 如果有多用户，记得传 user_id
    for record in unextracted_records:
        target_session_id = record['session_id']
        # 查询当前session_id下的所有对话消息
        msg = get_user_message(target_session_id)
        background_tasks.add_task(
            consolidate_session_to_ltm,
            session_id=target_session_id,
            ltm_json=ltm_json,
            session_msg=msg
        )
    return {"id": session_id, "title": "新旅行规划"}


@app.get("/api/history/{session_id}")
async def get_history(session_id: str):
    """
    重构后：直接从 MySQL 提取该会话的所有聊天记录。
    不再依赖 main_app.aget_state，查询效率更高。
    """
    try:
        # 从数据库获取原始记录
        # 这里的 get_messages_by_session 是同步函数，
        # 在 FastAPI 中可以用 run_in_threadpool 包装以避免阻塞，或直接调用
        db_messages = get_messages_by_session(session_id)

        if not db_messages:
            return {"messages": []}

        history = []
        for msg in db_messages:
            # db_messages 是字典列表，包含 role, content, msg_type 等字段
            history.append({
                "role": msg["role"],
                "content": msg["content"],
                "type": msg.get("msg_type", "text"),  # 扩展：支持返回消息类型
                "time": msg["created_at"].strftime("%Y-%m-%d %H:%M:%S") if msg.get("created_at") else ""
            })

        return {"messages": history}

    except Exception as e:
        print(f"获取历史记录失败: {e}")
        return {"messages": [], "error": "无法加载历史记录"}


@app.get("/")
async def get_index(request: Request):
    """渲染前端对话界面"""
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/api/chat")
async def chat_endpoint(
        background_tasks: BackgroundTasks,
        session_id: str = Form(...),
        message: str = Form(""),
        image: UploadFile = File(None)
):
    # 1. 准备配置信息（用于多轮记忆）
    config = {"configurable": {"thread_id": session_id}}

    # 2. 构建消息内容
    content = []
    if message:
        add_message(session_id=session_id, role="user", content=message, msg_type="text")
        content.append({"type": "text", "text": message})
    if image:
        # 1. 保存图片副本用于本地记录或 ImageAgent 分析
        os.makedirs("testimage", exist_ok=True)
        file_path = f"testimage/{image.filename}"
        # 优化读取与写入逻辑
        img_data = await image.read()
        with open(file_path, "wb+") as f:
            f.write(img_data)
        try:
            # 2. 💡 直接调用图像分析模块
            image_result = await analyze_travel_image(file_path)
            # 3. 💡 将多模态对象降维为纯文本描述
            image_context = (
                f"\n【系统提示：用户上传了一张参考图片，视觉专家已提取出以下线索】\n"
                f"1.提取到的想去的游玩地点：{image_result.location}\n"
                f"2.提取到的景点的环境氛围：{image_result.atmosphere}\n"
                f"3.提取到的景点的要求：{image_result.constraints}"  # 这里偷懒直接把整个 JSON 序列化放进去了
            )
            # 4. 追加到 content 中（下游的 LangGraph 节点现在只需要读纯文本就能懂图片内容了！）
            content.append({
                "type": "text",
                "text": image_context
            })
            print(f"    [Endpoint] ✅ 图片转换完毕！提取情报: {image_result}")

        except Exception as e:
            print(f"    [Endpoint] ❌ 图片分析失败: {e}")
            # 兜底逻辑：如果视觉模型报错，至少告诉下游主模型用户发了图片
            content.append({
                "type": "text",
                "text": "\n【系统提示：用户上传了一张图片，但视觉分析组件暂时离线，无法获取细节。】"
            })

    existing_state = await main_app.aget_state(config)
    old_summary = existing_state.values.get("memory_summary", "") if existing_state.values else ""
    print("existing_state:", existing_state)
    if not existing_state.values:
        print(f"\n[API] 🆕 触发首轮对话 (Session: {session_id})")

        # 💡 [首轮对话逻辑]
        # 1. 更新 MySQL 中的标题，方便左侧展示
        title_summary = message[:15] + "..." if len(message) > 15 else message
        update_session_title(session_id, title_summary)
        long_term_memory = ltm_json.load_profile()
        # 2. 注入全量初始状态（包含用户画像等背景知识）
        input_state = {
            "messages": [HumanMessage(content=content)],
            "user_profile": long_term_memory,
            "is_info_complete": False,
            "analyzer_count": 0,
            "next_node": ""
        }
    else:
        print(f"\n[API] 💬 触发多轮增量对话 (Session: {session_id})")
        input_state = {
            "messages": [HumanMessage(content=content)]
        }
    try:
        # 4. 调用 LangGraph 异步执行
        print("调用 LangGraph 异步执行")
        result = await main_app.ainvoke(input_state, config=config)
        print("调用 LangGraph 异步执行成功")

        new_summary = result.get("memory_summary", "")
        if new_summary and new_summary != old_summary:
            print(f"💾 [API] 检测到记忆发生压缩，仅将新摘要同步至 session_meta 表...")
            update_session_summary(session_id, new_summary)
        # 5. 逆向提取最后一条大模型生成的文字回复
        final_messages = result.get("messages", [])
        agent_reply = "系统处理完毕。"
        # 倒序查找，找到最后一条有实际内容的 AIMessage 回复给前端
        for msg in reversed(final_messages):
            if isinstance(msg, AIMessage) and msg.content:
                agent_reply = msg.content
                break
        add_message(session_id=session_id, role="bot", content=agent_reply, msg_type="text")

    except Exception as e:
        print("\n" + "=" * 50)
        print("❌ 报错啦！详细追踪信息如下：")
        traceback.print_exc()
        print("=" * 50 + "\n")
        agent_reply = "系统执行出错，请查看控制台日志。"
        # print(f"Error invoking graph: {e}")
        # agent_reply = f"系统执行出错: {str(e)}"

    return {
        "reply": agent_reply
    }


if __name__ == "__main__":
    print("🚀 Starting server at http://127.0.0.1:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
