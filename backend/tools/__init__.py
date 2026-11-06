"""工具实现模块。

当前包含：
- get_current_time_tool：获取当前真实时间。
- get_weather_tool：查询指定城市当前天气。
- recall_digest / recall_original：摘要优先的历史回忆，候选临时筛选后保留。
- web_search：DeepSeek 网页搜索、抓取与编号筛选。

具体工具类放在本目录；工具对象的集合入口在
backend.use_tools.get_tools 中。后续新增工具时，两处都需要更新。
本目录与 backend.llms、backend.memory、backend.use_tools 同级。
"""
