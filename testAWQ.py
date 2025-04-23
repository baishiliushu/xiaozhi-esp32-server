import os
from openai import OpenAI

# 初始化OpenAI客户端，配置本地部署的QWen服务
client = OpenAI(
    # 本地服务通常不需要API Key，或使用占位符。
    # 如果你的服务需要，请替换 "None"。
    # 如果完全不需要，也可以尝试省略 api_key 参数。
    api_key="mindo",
    base_url="http://192.168.50.208:8000/v1/",  # 更新为你的本地服务地址
)

# 定义可用工具列表 (与原代码相同)
tools = [
    # 工具1 获取当前时刻的时间
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "当你想知道现在的时间时非常有用。",
            "parameters": {}  # 无需参数
        }
    },
    # 工具2 获取指定城市的天气
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "当你想查询指定城市的天气时非常有用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "城市或县区，比如北京市、杭州市、余杭区等。"
                    }
                },
                "required": ["location"]  # 必填参数
            }
        }
    }
]

# 定义问题 (与原代码相同)
messages = [{"role": "user", "content": input("请输入问题：")}]

print("向本地模型服务发送请求...")
try:
    completion = client.chat.completions.create(
        model="QwQ-32B-AWQ",  # 更新为你的本地模型名称
        messages=messages,
        tools=tools,
        parallel_tool_calls=True,  # 确保你的本地服务支持并行工具调用
        stream=True,
        # 注意：stream_options 和 usage 可能不被所有本地服务支持
        # stream_options={
        #     "include_usage": True
        # }

    )

    reasoning_content = ""  # 定义完整思考过程
    answer_content = ""  # 定义完整回复
    tool_info = []  # 存储工具调用信息
    is_answering = False  # 判断是否结束思考过程并开始回复

    print("=" * 20 + "思考过程 (如果本地服务支持)" + "=" * 20)
    for chunk in completion:
        # print(f"DEBUG: Received chunk: {chunk}") # Debugging line
        if not chunk.choices:
            # 处理可能的用量统计信息 (如果本地服务支持)
            if hasattr(chunk, 'usage') and chunk.usage:
                print("\n" + "=" * 20 + "Usage" + "=" * 20)
                print(chunk.usage)
            continue  # 继续处理下一个chunk

        delta = chunk.choices[0].delta

        # 处理AI的思考过程（链式推理）- 可能不适用于所有本地服务
        if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
            reasoning_content += delta.reasoning_content
            print(delta.reasoning_content, end="", flush=True)  # 实时输出思考过程

        # 处理最终回复内容
        # 检查 delta.content 是否存在且不为 None
        if hasattr(delta, 'content') and delta.content is not None:
            if not is_answering and not reasoning_content:  # 如果没有思考过程，则在第一次收到内容时打印标题
                is_answering = True
                print("\n" + "=" * 20 + "回复内容" + "=" * 20)
            elif not is_answering and reasoning_content:  # 如果有思考过程，则在思考过程结束后打印标题
                is_answering = True
                print("\n" + "=" * 20 + "回复内容" + "=" * 20)

            answer_content += delta.content
            print(delta.content, end="", flush=True)  # 流式输出回复内容

        # 处理工具调用信息（支持并行工具调用）
        if hasattr(delta, 'tool_calls') and delta.tool_calls is not None:
            if not is_answering:  # 如果先收到工具调用信息，也视为回答阶段开始
                is_answering = True
                print("\n" + "=" * 20 + "回复内容 (包含工具调用)" + "=" * 20)

            for tool_call in delta.tool_calls:
                # tool_call 本身可能不完整，需要根据 index 聚合
                if tool_call.index is not None:  # 确保 index 存在
                    index = tool_call.index  # 工具调用索引，用于并行调用

                    # 动态扩展工具信息存储列表
                    while len(tool_info) <= index:
                        tool_info.append({'id': '', 'name': '', 'arguments': ''})  # 初始化字典确保键存在

                    # 收集工具调用ID（用于后续函数调用）
                    if tool_call.id:
                        # ID通常在第一个包含该index的chunk中完整提供，后续为None
                        # 这里简单覆盖，因为id通常只出现一次
                        tool_info[index]['id'] = tool_call.id

                        # 收集函数名称（用于后续路由到具体函数）
                    if tool_call.function and tool_call.function.name:
                        tool_info[index]['name'] += tool_call.function.name  # 累加函数名片段

                    # 收集函数参数（JSON字符串格式，需要后续解析）
                    if tool_call.function and tool_call.function.arguments:
                        tool_info[index]['arguments'] += tool_call.function.arguments  # 累加参数片段
                else:
                    # 处理没有 index 的情况，虽然在并行调用中不太常见
                    # 可以在这里添加警告或特定的处理逻辑
                    print(f"WARN: Received tool_call without index: {tool_call}")

    print(f"\n" + "=" * 19 + "工具调用信息" + "=" * 19)
    if not tool_info:
        print("没有工具调用")
    else:
        # 打印聚合后的工具调用信息
        for i, tool_call_data in enumerate(tool_info):
            print(f"Tool Call Index {i}:")
            print(f"  ID: {tool_call_data.get('id', 'N/A')}")
            print(f"  Name: {tool_call_data.get('name', 'N/A')}")
            print(f"  Arguments: {tool_call_data.get('arguments', 'N/A')}")
            # 可以尝试在这里解析 arguments JSON
            # import json
            # try:
            #     args = json.loads(tool_call_data.get('arguments', '{}'))
            #     print(f"  Parsed Arguments: {args}")
            # except json.JSONDecodeError:
            #     print("  Arguments are not valid JSON.")


except Exception as e:
    print(f"\n发生错误: {e}")
    print("请检查：")
    print(f"1. 本地服务是否在 http://192.168.50.208:8000 正常运行。")
    print(f"2. 模型名称 'QwQ-32B-AWQ' 是否正确且已被服务加载。")
    print(f"3. 网络连接是否通畅。")
    print(f"4. 服务是否正确实现了 OpenAI 兼容的 /v1/chat/completions 接口（包括流式传输和工具调用）。")