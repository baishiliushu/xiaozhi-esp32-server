import json
import httpx
from typing import Any
import os # 引入 os
import mcp
from mcp.server import FastMCP
from dotenv import load_dotenv # 引入 dotenv
import datetime # <--- 导入 datetime 模块

# 加载 .env 文件
load_dotenv()

mcp = FastMCP("ToolsServer") # 可以改个更通用的名字

print("ToolsServer started successfully")

OPENWEATHER_API_BASE = "https://api.openweathermap.org/data/2.5/weather"
# 从环境变量读取 API Key，提供一个默认的空值或测试值
API_KEY = os.getenv("OPENWEATHER_API_KEY", "YOUR_DEFAULT_OR_PLACEHOLDER_KEY")
if API_KEY == "YOUR_DEFAULT_OR_PLACEHOLDER_KEY":
    print("⚠️ 警告: OPENWEATHER_API_KEY 环境变量未设置，请在 .env 文件或环境中设置。")

USER_AGENT = "weather-app/1.0"

async def fetch_weather(city: str) -> dict[str, Any] | None:
    """
    从 OpenWeather API 获取天气信息。
    :param city: 城市名称（英文，例如 Beijing, London）
    :return: 天气数据字典；若出错返回包含 error 信息的字典
    """
    if not API_KEY or API_KEY == "YOUR_DEFAULT_OR_PLACEHOLDER_KEY":
        return {"error": "OpenWeather API Key 未配置。"}

    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric",
        "lang": "zh_cn"
    }
    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient() as client:
        try:
            print(f"  -> Fetching weather for: {city}") # 调试信息
            response = await client.get(OPENWEATHER_API_BASE, params=params, headers=headers, timeout=30.0)
            response.raise_for_status() # 对 4xx/5xx 状态码抛出异常
            data = response.json()
            print(f"  <- Received weather data: {str(data)[:100]}...") # 调试信息
            return data
        except httpx.HTTPStatusError as e:
            error_detail = f"HTTP 错误: {e.response.status_code}"
            try:
                 # 尝试解析 API 返回的错误信息
                 error_body = e.response.json()
                 error_detail += f" - {error_body.get('message', '未知 API 错误')}"
            except:
                 pass # 如果无法解析 JSON，就使用基本错误信息
            print(f"  <- Error fetching weather: {error_detail}")
            return {"error": error_detail}
        except httpx.RequestError as e: # 更具体的请求错误
             print(f"  <- Error fetching weather: 请求失败 - {str(e)}")
             return {"error": f"请求失败: {str(e)}"}
        except Exception as e:
             print(f"  <- Error fetching weather: 意外错误 - {str(e)}")
             return {"error": f"请求失败: {str(e)}"}


def format_weather(data: dict[str, Any] | str) -> str:
    """
    将天气数据格式化为易读文本。
    :param data: 天气数据（可以是字典或 JSON 字符串）
    :return: 格式化后的天气信息字符串
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
    if cod != 200: # OpenWeatherMap 用 cod 表示状态码
        return f"⚠️ 获取天气失败: {data.get('message', f'API 返回错误码 {cod}')}"

    city = data.get("name", "未知地点")
    country_data = data.get("sys", {})
    country = f", {country_data.get('country')}" if country_data.get('country') else ""

    main_data = data.get("main", {})
    temp = main_data.get("temp", "N/A")
    humidity = main_data.get("humidity", "N/A")

    wind_data = data.get("wind", {})
    wind_speed = wind_data.get("speed", "N/A")

    weather_list = data.get("weather", [{}])
    description = weather_list[0].get("description", "未知") if weather_list else "未知"

    return (
        f"🌍 地点: {city}{country}\n"
        f"🌤 天气: {description}\n"
        f"🌡 温度: {temp}°C\n"
        f"💧 湿度: {humidity}%\n"
        f"🌬 风速: {wind_speed} m/s"
    )

@mcp.tool()
async def query_weather(city: str) -> str:
    """
    查询指定城市的当前天气情况。城市名称需要是英文 (例如: 'Beijing', 'London')。
    :param city: 需要查询天气的城市英文名称。
    :return: 格式化后的天气信息字符串。
    """
    print(f"MCP Tool 'query_weather' called with city: '{city}'")
    if not isinstance(city, str) or not city:
        return "错误：需要提供有效的城市名称（字符串）。"
    data = await fetch_weather(city)
    formatted_result = format_weather(data)
    debug_message = formatted_result.replace('\n', ' ')  # 先执行替换操作
    print(f"  -> Returning formatted weather: {debug_message}")  # 再将结果放入 f-string
    return formatted_result

# --- 新增：获取当前时间的工具 ---
@mcp.tool()
async def get_current_server_time() -> str:
    """
    获取运行此工具的服务器上的当前日期和时间。不需要任何输入参数。
    :return: 格式为 'YYYY-MM-DD HH:MM:SS' 的当前时间字符串。
    """
    now = datetime.datetime.now()
    formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"MCP Tool 'get_current_server_time' called. Returning: {formatted_time}")
    return formatted_time

if __name__ == "__main__":
    print(f"正在启动 MCP Server (stdio)... API Key Loaded: {'Yes' if API_KEY and API_KEY != 'YOUR_DEFAULT_OR_PLACEHOLDER_KEY' else 'No'}")
    mcp.run(transport='stdio')