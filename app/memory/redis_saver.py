import os
from langgraph.checkpoint.redis import AsyncRedisSaver

REDIS_URL = os.getenv("REDIS_URL")
def get_redis_saver() -> AsyncRedisSaver:
    """
    返回一个持久化的 Redis Checkpointer 实例。
    LangGraph 会自动把 State 序列化并存入 Redis。
    """
    return AsyncRedisSaver(REDIS_URL)