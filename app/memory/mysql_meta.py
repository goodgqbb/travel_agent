import pymysql
import os
from dotenv import load_dotenv

load_dotenv()
# 请在你的 .env 文件中配置这些环境变量
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DB = os.getenv("MYSQL_DB")

def get_db_connection():
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        cursorclass=pymysql.cursors.DictCursor
    )


def init_mysql_db():
    """初始化数据库表（包含会话表和消息表）"""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # 1. 创建会话主表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_meta (
                session_id VARCHAR(64) PRIMARY KEY,
                title VARCHAR(255) DEFAULT '新旅行规划',
                memory_summary TEXT COMMENT '压缩后的记忆摘要',
                is_ltm_extracted TINYINT(1) DEFAULT 0 COMMENT '是否已提取长期记忆',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                is_deleted TINYINT(1) DEFAULT 0
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')

        # 2. 创建消息记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                session_id VARCHAR(64) NOT NULL,
                role VARCHAR(20) NOT NULL COMMENT '发送方: user 或 bot',
                content LONGTEXT NOT NULL COMMENT '消息体内容',
                msg_type VARCHAR(20) DEFAULT 'text' COMMENT '消息类型: text, image_url 等',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_session_id (session_id),
                FOREIGN KEY (session_id) REFERENCES session_meta(session_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')
    conn.commit()
    conn.close()


# LTM相关：

def get_unextracted_sessions(now_sessionid) -> list:
    """获取所有已完结但还没提取长期记忆的会话"""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT session_id FROM session_meta 
            WHERE is_ltm_extracted = 0 AND session_id !=%s
        ''', (now_sessionid,))
        records = cursor.fetchall()
    conn.close()
    return records


def mark_session_extracted(session_id: str):
    """标记会话已被提取过长期记忆"""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            'UPDATE session_meta SET is_ltm_extracted = 1 WHERE session_id = %s',
            (session_id,)
        )
    conn.commit()
    conn.close()


def get_user_message(session_id: str) -> str:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 仅 Select 我们需要的 role 和 content 字段，并根据创建时间升序排列
            cursor.execute(
                '''
                SELECT role, content 
                FROM chat_messages 
                WHERE session_id = %s AND role = 'user'
                ORDER BY created_at ASC
                ''',
                (session_id,)
            )
            messages = cursor.fetchall()
        formatted_messages = []
        for msg in messages:
            content = msg.get('content', '')
            if content.strip():  # 过滤掉可能的空消息
                formatted_messages.append(f"user: {content}")

        # 用换行符将所有消息连接起来
        history_str = "\n".join(formatted_messages)

        return history_str
    except Exception as e:
        print(f"❌ 获取会话 {session_id} 的消息失败: {e}")
        return []
    finally:
        conn.close()


# -------- 会话相关的操作保持不变 --------

def create_session(session_id: str):
    """新建会话"""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO session_meta (session_id) VALUES (%s)',
            (session_id,)
        )
    conn.commit()
    conn.close()


def update_session_title(session_id: str, title: str):
    """更新会话标题"""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            'UPDATE session_meta SET title = %s WHERE session_id = %s',
            (title, session_id)
        )
    conn.commit()
    conn.close()


def update_session_summary(session_id: str, summary: str):
    """更新会话的记忆摘要（仅更新 session_meta，不碰 chat_messages）"""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            'UPDATE session_meta SET memory_summary = %s WHERE session_id = %s',
            (summary, session_id)
        )
    conn.commit()
    conn.close()


def get_active_sessions():
    """获取所有未删除的会话列表"""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            'SELECT session_id, title, updated_at FROM session_meta WHERE is_deleted = 0 ORDER BY updated_at DESC'
        )
        sessions = cursor.fetchall()
    conn.close()
    return sessions


# -------- 新增：消息相关的操作 --------

def add_message(session_id: str, role: str, content: str, msg_type: str = "text"):
    """
    保存单条消息到数据库
    :param session_id: 会话ID
    :param role: 发送者角色 ('user' 或 'bot')
    :param content: 消息内容（支持 Base64 字符串或者普通文本）
    :param msg_type: 消息格式类型
    """
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            '''
            INSERT INTO chat_messages (session_id, role, content, msg_type) 
            VALUES (%s, %s, %s, %s)
            ''',
            (session_id, role, content, msg_type)
        )
        # 可选：插入新消息时自动更新会话的 updated_at，使活跃会话排在前面
        cursor.execute(
            'UPDATE session_meta SET updated_at = CURRENT_TIMESTAMP,is_ltm_extracted = 0 WHERE session_id = %s',
            (session_id,)
        )
    conn.commit()
    conn.close()


def get_messages_by_session(session_id: str):
    """获取指定会话的所有历史消息，按时间先后排序"""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            '''
            SELECT role, content, msg_type, created_at 
            FROM chat_messages 
            WHERE session_id = %s 
            ORDER BY created_at ASC
            ''',
            (session_id,)
        )
        messages = cursor.fetchall()
    conn.close()
    return messages
