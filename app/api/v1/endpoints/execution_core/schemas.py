"""执行链路端点请求模型（从 _helpers.py 拆出，schema 属端点层保留）。"""

from pydantic import BaseModel, Field


class SpeedReplayRequest(BaseModel):
    speed: float = Field(1.0, description="播放速度倍率")
