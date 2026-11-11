"""AI 调用计费单价常量（R4-7）。

独立成模块的原因：`openai_client`（同步）与 `_openai_async_client`（异步）
互相需要对方的符号——同步客户端在文件末尾导入异步客户端类，异步客户端
需要本文件的单价常量。把常量下沉到此处后，两者都只依赖 `_costs`，
导入图为单向，不再形成运行时循环依赖。
"""

_COST_PER_1K_PROMPT = 0.0014
_COST_PER_1K_COMPLETION = 0.0028
