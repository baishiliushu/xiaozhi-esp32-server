import os
import json
import datetime
import asyncio
import httpx
import uuid # 导入 uuid 来生成 tool_call_id
from openai import OpenAI
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# --- 从天气 API 脚本复制过来的核心逻辑 ---

OPENWEATHER_API_BASE = "https://api.openweathermap.org/data/2.5/weather"
# 从环境变量读取 API Key
API_KEY = os.getenv("OPENWEATHER_API_KEY")
if not API_KEY:
    print("⚠️ 警告: OPENWEATHER_API_KEY 环境变量未设置，请在 .env 文件或环境中设置。天气查询将失败。")
    API_KEY="YOUR_DEFAULT_OR_PLACEHOLDER_KEY" # 设置一个占位符避免后续检查报错

USER_AGENT = "weather-app/1.0"

async def fetch_weather(city: str) -> dict | None:
    """
    从 OpenWeather API 获取天气信息。
    :param city: 城市名称（英文或拼音可能效果更好，具体看API支持）
    :return: 天气数据字典；若出错返回包含 error 信息的字典
    """
    if API_KEY == "YOUR_DEFAULT_OR_PLACEHOLDER_KEY":
        return {"error": "OpenWeather API Key 未配置。"}

    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric", # 获取摄氏度
        "lang": "zh_cn"    # 获取中文描述
    }
    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient() as client:
        try:
            print(f"  -> [API Call] Fetching weather for: {city}")
            response = await client.get(OPENWEATHER_API_BASE, params=params, headers=headers, timeout=15.0) # 设置超时
            response.raise_for_status()
            data = response.json()
            print(f"  <- [API Call] Received weather data.")
            return data
        except httpx.HTTPStatusError as e:
            error_detail = f"HTTP 错误: {e.response.status_code}"
            try:
                 error_body = e.response.json()
                 error_detail += f" - {error_body.get('message', '未知 API 错误')}"
            except:
                 pass
            print(f"  <- [API Call] Error fetching weather: {error_detail}")
            return {"error": error_detail}
        except httpx.RequestError as e:
             print(f"  <- [API Call] Error fetching weather: 请求失败 - {str(e)}")
             return {"error": f"请求失败: {str(e)}"}
        except Exception as e:
             print(f"  <- [API Call] Error fetching weather: 意外错误 - {str(e)}")
             return {"error": f"意外错误: {str(e)}"}


def format_weather(data: dict | str) -> str:
    """
    将天气数据格式化为易读文本。
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception as e:
            return f"无法解析天气数据: {e}"

    if not isinstance(data, dict):
        return "错误：天气数据格式无效。"

    if "error" in data:
        return f"⚠️ 获取天气失败: {data['error']}"

    cod = data.get("cod")
    if str(cod) != '200': # API 返回的 cod 可能是数字或字符串 '200'
        return f"⚠️ 获取天气失败: {data.get('message', f'API 返回错误码 {cod}')}"

    city = data.get("name", "未知地点")
    country_data = data.get("sys", {})
    country = f", {country_data.get('country')}" if country_data.get('country') else ""

    main_data = data.get("main", {})
    temp = main_data.get("temp", "N/A")
    feels_like = main_data.get("feels_like", "N/A") # 体感温度
    humidity = main_data.get("humidity", "N/A")

    wind_data = data.get("wind", {})
    wind_speed = wind_data.get("speed", "N/A")

    weather_list = data.get("weather", [{}])
    description = weather_list[0].get("description", "未知") if weather_list else "未知"

    # 返回更详细、更自然的格式
    return (
        f"{city}{country} 当前天气：{description}，"
        f"温度 {temp}°C (体感温度 {feels_like}°C)，"
        f"湿度 {humidity}%，"
        f"风速 {wind_speed} m/s。"
    )

# --- 本地函数实现 ---
def get_current_time_local():
    """获取当前本地时间"""
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")

# !! 修改这里：创建一个同步包装器来调用异步的天气函数 !!
def execute_get_current_weather(location: str) -> str:
    """
    同步执行异步的天气查询并格式化结果。
    这个函数将由函数调用循环直接调用。
    """
    print(f"--- [Executor] Received request for weather in: '{location}' ---")
    if not isinstance(location, str) or not location:
        return "错误：需要提供有效的城市名称（字符串）。"

        # === 新增：城市名称转换 ===
    api_location = location  # 默认使用原始名称
    if location == "北京" or "beijing" in location.lower():  # 简单判断
        api_location = "Beijing"
        print(f"  -> [Mapping] Converted '{location}' to '{api_location}' for API call.")
    elif location == "上海" or "shanghai" in location.lower():
        api_location = "Shanghai"
        print(f"  -> [Mapping] Converted '{location}' to '{api_location}' for API call.")
    elif location == "杭州" or "hangzhou" in location.lower():
        api_location = "Hangzhou"
        print(f"  -> [Mapping] Converted '{location}' to '{api_location}' for API call.")
    # 你可以在这里添加更多城市的映射
    # ===========================

    try:
        # 使用转换后的名称调用 API
        weather_data = asyncio.run(fetch_weather(city=api_location))
        formatted_result = format_weather(weather_data)
        print(f"--- [Executor] Formatted result: {formatted_result.replace(os.linesep, ' ')}")
        return formatted_result
    except Exception as e:
        print(f"--- [Executor] Error during weather execution: {e}")
        return f"执行天气查询时出错: {str(e)}"

# --- 映射工具名称到本地执行函数 ---
available_functions = {
    "get_current_time": get_current_time_local,
    "get_current_weather": execute_get_current_weather,  # 保持不变，指向修改后的函数
}

# --- 初始化 OpenAI 客户端 (同步版本) ---
# 注意：为了简单起见，我们使用同步的 OpenAI 客户端。
# 如果你的应用是完全异步的，需要调整函数调用循环部分。
client = OpenAI(
    api_key="mindo",
    base_url="http://192.168.50.208:8000/v1/",
)

# --- 定义可用工具列表 (与之前相同) ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "当你想知道现在的时间时非常有用。",
            "parameters": {}
        }
    },
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
                        "description": "城市或县区，比如北京市、杭州市、深圳。(请注意API可能对中文地名支持有限，尝试拼音或英文)"
                    }
                },
                "required": ["location"]
            }
        }
    }
]

# 加载 .env 文件
load_dotenv()
API_KEY = os.getenv("OPENWEATHER_API_KEY", "YOUR_DEFAULT_OR_PLACEHOLDER_KEY")
if API_KEY == "YOUR_DEFAULT_OR_PLACEHOLDER_KEY":
     print("⚠️ 警告: OPENWEATHER_API_KEY 环境变量未设置。")


# --- 获取用户输入 ---
user_input = input("请输入问题：")
messages = [{"role": "user", "content": user_input}]

print("\n=== 第 1 步：向 LLM 发送请求，让其判断是否调用工具 ===")
try:
    with client.chat.completions.create(
        model="QwQ-32B-AWQ",
        messages=messages,
        tools=tools,
        tool_choice="auto",
        stream=True,
    ) as stream:

        assistant_message_content = ""
        tool_calls_aggregated = []
        current_tool_calls_buffer = {}

        print("--- LLM 响应流 (第一步) ---")
        for chunk in stream:
            if not chunk.choices: continue
            delta = chunk.choices[0].delta
            if not delta: continue # Add check for empty delta

            if delta.content:
                assistant_message_content += delta.content
                print(delta.content, end="", flush=True)

            if delta.tool_calls:
                for tool_call_chunk in delta.tool_calls:
                    index = tool_call_chunk.index
                    if index not in current_tool_calls_buffer:
                         current_tool_calls_buffer[index] = {
                            "id": None, "type": "function",
                            "function": {"name": "", "arguments": ""}
                         }
                    if tool_call_chunk.id:
                         current_tool_calls_buffer[index]["id"] = tool_call_chunk.id
                    if tool_call_chunk.function and tool_call_chunk.function.name:
                         current_tool_calls_buffer[index]["function"]["name"] += tool_call_chunk.function.name
                    if tool_call_chunk.function and tool_call_chunk.function.arguments:
                         current_tool_calls_buffer[index]["function"]["arguments"] += tool_call_chunk.function.arguments

        print("\n--- 第一步响应处理完毕 ---")

        tool_calls_aggregated = [tc for idx, tc in sorted(current_tool_calls_buffer.items())]

        # === 修改后的逻辑：检查 tool_calls 或 content ===
        parsed_tool_call_from_content = None
        if not tool_calls_aggregated and assistant_message_content:
            # 如果 tool_calls 为空，但 content 不为空，尝试从中解析工具调用 JSON
            try:
                # 尝试移除可能的标记并解析 JSON (更鲁棒的方式是正则匹配)
                potential_json_str = assistant_message_content.strip().replace("</tool_call>", "")
                # 寻找第一个 '{' 和最后一个 '}' 之间的内容
                start_idx = potential_json_str.find('{')
                end_idx = potential_json_str.rfind('}')
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    json_str_to_parse = potential_json_str[start_idx : end_idx + 1]
                    parsed_data = json.loads(json_str_to_parse)
                    # 检查解析后的数据是否像工具调用
                    if isinstance(parsed_data, dict) and "name" in parsed_data and "arguments" in parsed_data:
                        print(f"  [Info] 检测到工具调用信息在 content 中，尝试解析: {json_str_to_parse}")
                        # 为其生成一个 ID，并构造成标准格式
                        parsed_tool_call_from_content = {
                            "id": f"tool_{uuid.uuid4().hex[:8]}", # 生成唯一 ID
                            "type": "function",
                            "function": parsed_data # 直接使用解析出的 name 和 arguments
                        }
                        # 清空 assistant_message_content，因为它实际上是工具调用指令
                        assistant_message_content = ""
            except json.JSONDecodeError:
                print(f"  [Info] content 中包含非工具调用JSON的文本: {assistant_message_content}")
                pass # 解析失败，说明 content 不是工具调用 JSON
            except Exception as e:
                print(f"  [Warning] 解析 content 中的工具调用时发生意外错误: {e}")
                pass


        # === 判断是否需要执行工具（优先级：标准 tool_calls > 从 content 解析的）===
        if tool_calls_aggregated or parsed_tool_call_from_content:
            print(f"\n=== 第 2 步：LLM 请求调用工具，开始执行本地函数 ===")

            final_tool_calls_to_execute = tool_calls_aggregated # 优先使用标准的 tool_calls
            if not final_tool_calls_to_execute and parsed_tool_call_from_content:
                 final_tool_calls_to_execute = [parsed_tool_call_from_content] # 如果标准为空，使用从 content 解析的

                 # === 新增：格式化 tool_calls 以符合 API 要求 ===
                 assistant_tool_calls_for_history = []
                 if final_tool_calls_to_execute:
                     for tc in final_tool_calls_to_execute:
                         # 确保 arguments 是 JSON 字符串
                         args_str = json.dumps(tc['function']['arguments'], ensure_ascii=False) \
                             if isinstance(tc['function']['arguments'], dict) \
                             else tc['function']['arguments']  # 如果已经是字符串则不变
                         assistant_tool_calls_for_history.append({
                             "id": tc['id'],
                             "type": tc['type'],
                             "function": {
                                 "name": tc['function']['name'],
                                 "arguments": args_str  # <--- 必须是字符串
                             }
                         })
                 # ================================================
                
            # 1. 将 LLM 的回复添加到消息历史中
            messages.append({
                "role": "assistant",
                "content": assistant_message_content if assistant_message_content else None,
                 # 使用最终确定要执行的工具调用列表
                "tool_calls": final_tool_calls_to_execute if final_tool_calls_to_execute else None
            })

            # 2. 循环执行工具调用
            tool_results = []
            for tool_call in final_tool_calls_to_execute:
                # ... (执行本地函数的逻辑保持不变) ...
                function_name = tool_call["function"]["name"]
                tool_call_id = tool_call["id"] # 现在 ID 可能是生成的
                function_args_str = tool_call["function"]["arguments"]

                if function_name in available_functions:
                    function_to_call = available_functions[function_name]
                    try:
                        # 如果参数已经是字典 (来自 content 解析)，则无需再次 loads
                        if isinstance(function_args_str, dict):
                             function_args = function_args_str
                        else:
                             function_args = json.loads(function_args_str)

                        print(f"  调用本地函数: {function_name}，参数: {function_args}")
                        function_response = function_to_call(**function_args)
                        print(f"  本地函数 '{function_name}' 返回 (类型: {type(function_response)})")
                        tool_results.append({
                            "role": "tool", "tool_call_id": tool_call_id,
                            "content": str(function_response), # 确保是字符串
                        })
                    # ... (错误处理逻辑保持不变) ...
                    except json.JSONDecodeError:
                        print(f"  错误: 无法解析函数 '{function_name}' 的参数 JSON: {function_args_str}")
                        tool_results.append({
                            "role": "tool", "tool_call_id": tool_call_id,
                            "content": f"Error: Invalid JSON arguments for {function_name}",
                        })
                    except Exception as e:
                        print(f"  错误: 调用函数 '{function_name}' 时出错: {e}")
                        tool_results.append({
                            "role": "tool", "tool_call_id": tool_call_id,
                            "content": f"Error executing function {function_name}: {str(e)}",
                        })
                else:
                    print(f"  错误: 未知的函数名称: {function_name}")
                    tool_results.append({
                        "role": "tool", "tool_call_id": tool_call_id,
                        "content": f"Error: Function {function_name} not found.",
                    })


            # 3. 将结果添加到历史
            messages.extend(tool_results)

            print("\n=== 第 3 步：将工具执行结果发回 LLM，获取最终回复 ===")
            # ... (第二次 LLM 调用逻辑保持不变) ...
            try:
                with client.chat.completions.create(
                    model="QwQ-32B-AWQ",
                    messages=messages,
                    stream=True,
                ) as second_stream:
                    # ... (处理最终回复流的逻辑不变) ...
                    print("--- LLM 最终回复流 ---")
                    final_answer = ""
                    for chunk in second_stream:
                         if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                            content_piece = chunk.choices[0].delta.content
                            final_answer += content_piece
                            print(content_piece, end="", flush=True)
                    print("\n--- 最终回复处理完毕 ---")
                    print(f"\n最终完整回复文本: {final_answer}")

            except Exception as e:
                print(f"\n第二次调用 LLM 时发生错误: {e}")

        else:
            # 如果标准的 tool_calls 和从 content 解析的 tool_call 都没有
            print("\n=== LLM 未请求调用工具，直接输出回复 ===")
            print(f"最终回复: {assistant_message_content}")

except Exception as e:
    print(f"\n第一次调用 LLM 时发生错误: {e}")
    # ... (错误提示) ...