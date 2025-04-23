import os
import requests
import json

# 定义服务器信息
BASE_URL = "http://192.168.50.208:8000/v1/chat/completions"
API_KEY = "mindo"  # 替换为实际的 API Key
MODEL_NAME = "QwQ-32B-AWQ"

# 定义请求消息
messages = [
    {'role': 'user', 'content': '哪吒2的票房'}
]

# 构造请求体
data = {
    "model": MODEL_NAME,
    "messages": messages,
    "stream": True,  # 开启流式输出
    "enable_search": True,  # 开启联网搜索
    "search_options": {
        "forced_search": True,  # 强制开启联网搜索
        "enable_source": True,  # 返回搜索来源信息
        "enable_citation": True,  # 开启角标标注功能
        "citation_format": "[ref_<number>]",  # 角标形式
        "search_strategy": "pro"  # 搜索策略
    }
}

# 设置请求头
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 发送请求
response = requests.post(BASE_URL, headers=headers, json=data, stream=True)

# 初始化变量
reasoning_content = ""
answer_content = ""
is_answering = False
is_first_chunk = True

print("=" * 20 + "搜索信息" + "=" * 20)

for line in response.iter_lines(decode_unicode=True):
    if line:
        try:
            # 提取 `data:` 后面的内容
            if line.startswith("data: "):
                line = line[6:]  # 去掉 "data: " 前缀
            chunk = json.loads(line)  # 解析 JSON 数据

            # 打印原始数据以调试
            print(f"原始数据: {chunk}")

            # 检查是否包含搜索信息
            if is_first_chunk and "output" in chunk and "search_info" in chunk["output"]:
                search_results = chunk["output"]["search_info"].get("search_results", [])
                for web in search_results:
                    print(f"[{web['index']}]: [{web['title']}]({web['url']})")
                print("=" * 20 + "思考过程" + "=" * 20)
                reasoning_content += chunk["output"]["choices"][0]["message"].get("reasoning_content", "")
                print(chunk["output"]["choices"][0]["message"].get("reasoning_content", ""), end="", flush=True)
                is_first_chunk = False
            else:
                # 如果思考过程与回复皆为空，则忽略
                message = chunk["output"]["choices"][0]["message"]
                if (message.get("content", "") == "" and message.get("reasoning_content", "") == ""):
                    pass
                else:
                    # 如果当前为思考过程
                    if (message.get("reasoning_content", "") != "" and message.get("content", "") == ""):
                        print(message.get("reasoning_content", ""), end="", flush=True)
                        reasoning_content += message.get("reasoning_content", "")
                    # 如果当前为回复
                    elif message.get("content", "") != "":
                        if not is_answering:
                            print("\n" + "=" * 20 + "完整回复" + "=" * 20)
                            is_answering = True
                        print(message.get("content", ""), end="", flush=True)
                        answer_content += message.get("content", "")

        except json.JSONDecodeError as e:
            print(f"JSON 解码失败: {e}")
            continue

# 打印完整思考过程与完整回复（可选）
print("\n" + "=" * 20 + "完整思考过程" + "=" * 20 + "\n")
print(reasoning_content)
print("\n" + "=" * 20 + "完整回复" + "=" * 20 + "\n")
print(answer_content)

# 打印 Token 消耗（可选）
if "usage" in chunk:
    print("\n" + "=" * 20 + "Token 消耗" + "=" * 20)
    print(chunk["usage"])