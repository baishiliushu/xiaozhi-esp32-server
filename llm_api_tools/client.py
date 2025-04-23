import asyncio
import os
import json
import sys
import aiohttp
from typing import Optional, List, Dict, Any
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client # 确保这个导入也在

from dotenv import load_dotenv # 引入 dotenv

# 加载 .env 文件
load_dotenv()

class LocalMCPClient:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        # --- vLLM Configuration ---
        # 从环境变量读取，如果未设置则使用默认值（或抛出错误）
        self.vllm_api_url = os.getenv("VLLM_API_URL", "http://192.168.50.205:8000/v1/chat/completions") # 使用环境变量 VLLM_API_URL
        self.model_name = os.getenv("MODEL_NAME", "QW1.5BIns") # 使用环境变量 MODEL_NAME

        if not self.vllm_api_url:
            raise ValueError("❌ VLLM API URL 未设置。请在 .env 文件中设置 VLLM_API_URL 或直接在代码中提供默认值。")
        if not self.model_name:
            print("⚠️ MODEL_NAME 未设置，将使用 vLLM 默认模型（如果支持）。")
            # 或者 raise ValueError("❌ MODEL_NAME 未设置。")

        self.mcp_session: Optional[ClientSession] = None # MCP Session
        self.mcp_tools: list = [] # 修改后的代码 (推荐)
        self.http_session: Optional[aiohttp.ClientSession] = None  # For async HTTP requests
        self.chat_history: List[Dict[str, Any]] = [] # 存储对话历史

    async def initialize_http_session(self):
        """初始化 aiohttp 会话并添加到退出栈"""
        if not self.http_session:
            self.http_session = aiohttp.ClientSession()
            await self.exit_stack.enter_async_context(self.http_session)

    async def connect_to_mcp_server(self, server_script_path: str):
        """连接到 MCP 服务器并获取工具列表"""
        if not os.path.isfile(server_script_path):
             raise FileNotFoundError(f"MCP Server 脚本未找到: {server_script_path}")

        print(f"尝试连接到 MCP Server 脚本: {server_script_path}...")
        is_python = server_script_path.endswith('.py')
        command = "python" if is_python else "node" # 假设是 Python 脚本

        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=os.environ.copy() # 传递当前环境变量给子进程
        )

        try:
             # 启动 MCP 服务器并建立通信
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            stdio_reader, stdio_writer = stdio_transport

            # 创建 MCP 客户端会话并添加到退出栈
            self.mcp_session = ClientSession(stdio_reader, stdio_writer)
            await self.exit_stack.enter_async_context(self.mcp_session)

            await self.mcp_session.initialize()

            # 列出并存储 MCP 服务器上的工具
            response = await self.mcp_session.list_tools()
            self.mcp_tools = response.tools
            if not self.mcp_tools:
                 print("⚠️ MCP Server 未报告任何可用工具。")
            else:
                 print("\n✅ 已连接到 MCP Server，支持以下工具:", [tool.name for tool in self.mcp_tools])

        except Exception as e:
            print(f"❌ 连接到 MCP Server 失败: {e}")
            raise # 重新抛出异常，让程序知道连接失败

    async def call_vllm_api(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """调用 vLLM 的 OpenAI 兼容 API"""
        if not self.http_session:
            await self.initialize_http_session()

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": 1024, # 可以调整
            "temperature": 0.5, # 可以调整
        }
        # --- 结束调试 ---
            # --- 添加/确保这行代码存在 ---
        headers = {"Content-Type": "application/json"}
        # --- 结束添加 ---

        print(f"\n🔄 正在向 vLLM 发送请求 ({self.vllm_api_url})...")
        # print(f"Payload (部分): model={payload['model']}, messages_count={len(payload['messages'])}, has_tools={bool(tools)}") # 调试信息
        try:
            async with self.http_session.post(self.vllm_api_url, headers=headers, json=payload,
                                              timeout=120) as response:
                if response.status == 200:
                    result = await response.json()
                    # --- 添加这行打印 ---
                    print(f"\n🔍 原始 vLLM 响应:\n{json.dumps(result, indent=2, ensure_ascii=False)}\n")
                    # --- 结束添加 ---
                    return result
                else:
                    error_text = await response.text()
                    print(f"❌ vLLM API 请求失败。状态码: {response.status}")
                    print(f"   URL: {self.vllm_api_url}")
                    # print(f"   Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}") # 失败时打印完整Payload
                    print(f"   响应内容: {error_text[:1000]}...") # 打印部分错误信息
                    return None
        except aiohttp.ClientConnectorError as e:
             print(f"❌ 连接错误: 无法连接到 vLLM API at {self.vllm_api_url}: {e}")
             return None
        except asyncio.TimeoutError:
             print(f"❌ 超时错误: 调用 vLLM API 超时 ({self.vllm_api_url})")
             return None
        except Exception as e:
            print(f"❌ 调用 vLLM API 时发生意外错误: {e}")
            return None

    async def process_query(self, query: str) -> Optional[str]:
        """
        处理查询，可能调用 MCP 工具，并返回最终的文本响应。
        """
        if not self.http_session:
            await self.initialize_http_session()  # 确保 http 会话已初始化

        # 1. 准备初始消息和可用工具列表
        # --- 添加 System Prompt ---
        # --- 修改后的 System Prompt ---
        system_message = {
            "role": "system",
            "content": """You are a helpful assistant. You have access to the following tools to obtain real-time information:

1.  **query_weather**:
    *   Description: 查询指定城市的当前实时天气情况。城市名称需要是英文 (例如: 'Beijing', 'London')。
    *   Arguments: `city` (string, required) - 需要查询天气的城市英文名称。

2.  **get_current_server_time**:
    *   Description: 获取运行此工具的服务器上的当前日期和时间。不需要任何输入参数。
    *   Arguments: None

**重要指令:**
当你需要使用工具来回答用户的问题时：
1.  判断需要哪个工具。
2.  提取必要的参数（如果是 `query_weather`，需要英文城市名）。
3.  **不要**直接回答问题。
4.  作为替代，你**必须**回复，并且**只回复**以下格式的 JSON 对象，不能包含任何其他文字、解释或前缀/后缀：

    *   **如果需要调用 `query_weather`:**
        ```json
        {
          "tool_name": "query_weather",
          "tool_arguments": {
            "city": "<这里是英文城市名>"
          }
        }
        ```
        (将 `<这里是英文城市名>` 替换为实际英文城市名)

    *   **如果需要调用 `get_current_server_time`:**
        ```json
        {
          "tool_name": "get_current_server_time",
          "tool_arguments": {}
        }
        ```
        (参数为空对象 `{}`)

**示例:**
- 用户问：“北京天气如何？”，你的回答**必须**是：
  ```json
  {
    "tool_name": "query_weather",
    "tool_arguments": {
      "city": "Beijing"
    }
  }
  用户问：“现在几点了？”，你的回答必须是：
  {
  "tool_name": "get_current_server_time",
  "tool_arguments": {}
  }
        如果用户的问题不需要使用工具（例如问候、常识性问题等），请像一个普通的助手那样直接回答。
"""
        }

        # --- 结束添加 ---

        current_turn_messages = []
        # 确保 System Prompt 在最前面
        if not self.chat_history or self.chat_history[0].get("role") != "system":
            current_turn_messages.append(system_message)
        elif self.chat_history and self.chat_history[0].get("role") == "system":
            # 如果历史记录里已有系统消息，用最新的替换（或保持不变）
            current_turn_messages.append(system_message)  # 总是使用最新的系统消息定义
            current_turn_messages.extend(self.chat_history[1:])  # 添加除旧系统消息外的历史
        else:
            current_turn_messages.extend(self.chat_history)

        current_turn_messages.append({"role": "user", "content": query})

        # 2. 第一次调用 LLM (不传 tools)
        llm_response_data = await self.call_vllm_api(current_turn_messages)

        if not llm_response_data or not llm_response_data.get("choices"):
            return "抱歉，我在思考时遇到了一些麻烦。"  # 不修改历史

        choice = llm_response_data["choices"][0]
        message = choice["message"]
        llm_content = message.get("content", "").strip()

        # 3. 将用户消息和助手响应（可能含JSON）添加到主历史记录
        #    注意：先不加 user message，等处理完再一起加，避免失败时留下记录
        # self.chat_history.append({"role": "user", "content": query}) # 暂时注释
        # self.chat_history.append(message) # 暂时注释

        # 4. 尝试解析 JSON 工具调用
        is_tool_call_parsed = False
        final_response_content = None  # 用于存储最终的回复

        try:
            pure_json_str = llm_content
            if pure_json_str.startswith("```json"):
                pure_json_str = pure_json_str[len("```json"):].strip()
            if pure_json_str.endswith("```"):
                pure_json_str = pure_json_str[:-len("```")].strip()

            tool_call_data = json.loads(pure_json_str)

            if isinstance(tool_call_data, dict) and \
                    "tool_name" in tool_call_data and \
                    "tool_arguments" in tool_call_data:

                tool_name = tool_call_data.get("tool_name")
                tool_args = tool_call_data.get("tool_arguments", {})  # 默认为空字典

                # 检查工具是否存在于 MCP Server 报告的列表中 (更健壮)
                available_tool_names = [t.name for t in self.mcp_tools]
                if tool_name in available_tool_names:
                    is_tool_call_parsed = True  # 标记已解析成功
                    print(f"\n🛠️ 解析到工具调用请求: {tool_name} (参数: {tool_args})")

                    # 5. 调用 MCP 工具
                    if self.mcp_session:
                        try:
                            print(f"   📞 正在调用 MCP 工具 '{tool_name}'...")
                            mcp_result = await self.mcp_session.call_tool(tool_name, tool_args)
                            tool_content = mcp_result.content[0].text if mcp_result.content else "工具未返回任何内容。"
                            print(f"   ✅ 工具执行结果: {tool_content}")  # 打印完整结果

                            # 6. 准备工具结果消息并添加到历史
                            tool_result_message_for_history = {
                                # 使用 user role 来告知 LLM 结果，通常更可靠
                                "role": "user",
                                "content": f"工具 '{tool_name}' 已执行，参数为 {tool_args}。 返回结果如下：\n---\n{tool_content}\n---\n请根据这个结果，用自然语言回答我最初的问题 ('{query}')。"
                            }
                            # 将用户、助手(JSON)、工具结果消息一起加入历史
                            self.chat_history.append({"role": "user", "content": query})
                            self.chat_history.append(message)  # 助手的 JSON 输出
                            self.chat_history.append(tool_result_message_for_history)

                            # 7. 第二次调用 LLM 获取最终回复
                            second_call_messages = []
                            if self.chat_history[0].get("role") != "system":
                                second_call_messages.append(system_message)  # 确保 System Prompt 还在
                            second_call_messages.extend(self.chat_history)  # 包含到工具结果的所有历史

                            print("🔄 正在将工具结果发送回 LLM 以生成最终回复...")
                            final_response_data = await self.call_vllm_api(second_call_messages)

                            if final_response_data and final_response_data.get("choices"):
                                final_message = final_response_data["choices"][0]["message"]
                                self.chat_history.append(final_message)  # 添加最终回复到历史
                                final_response_content = final_message.get("content")
                            else:
                                final_response_content = "抱歉，我获取了信息，但在总结时遇到了麻烦。"
                                # 可以考虑是否将最后一次失败的助手消息加入历史

                        except Exception as e:
                            print(f"   ❌ 执行 MCP 工具 '{tool_name}' 时出错: {e}")
                            # 将用户、助手(JSON)、错误消息加入历史
                            self.chat_history.append({"role": "user", "content": query})
                            self.chat_history.append(message)
                            self.chat_history.append({"role": "user", "content": f"执行工具 '{tool_name}' 时出错: {e}"})
                            final_response_content = f"抱歉，在尝试使用工具 '{tool_name}' 时发生了错误：{e}"
                    else:
                        # MCP 会话不存在
                        self.chat_history.append({"role": "user", "content": query})
                        self.chat_history.append(message)
                        self.chat_history.append({"role": "user", "content": "错误：无法调用工具，MCP会话未建立。"})
                        final_response_content = "错误：无法调用工具，MCP会话未建立。"
                else:
                    # 解析到 tool_name 但该工具不可用
                    print(f"⚠️ LLM 请求了不可用的工具: {tool_name}")
                    # 仍然当作普通消息处理，或者给出特定错误
                    pass  # 下面的代码会处理 is_tool_call_parsed = False 的情况

            else:
                # JSON 格式不符合预期
                print("⚠️ LLM 返回了 JSON，但格式不符合工具调用规范。")
                pass  # 下面的代码会处理 is_tool_call_parsed = False 的情况

        except json.JSONDecodeError:
            # 如果 llm_content 不是有效的 JSON
            print("➡️ LLM 未返回 JSON 工具调用，视为普通回复。")
            pass  # 下面的代码会处理 is_tool_call_parsed = False 的情况
        except Exception as e:
            # 处理其他潜在错误
            print(f"⚠️ 解析 LLM 响应或处理工具调用时发生错误: {e}")
            import traceback
            print(traceback.format_exc())
            # 记录用户消息和错误
            self.chat_history.append({"role": "user", "content": query})
            # 不记录可能有问题的助手消息 message
            self.chat_history.append({"role": "user", "content": f"处理回复时发生错误: {e}"})
            final_response_content = f"处理回复时发生错误: {e}"

        # 8. 如果没有成功解析并执行工具调用，则将原始回复视为最终回复
        if not is_tool_call_parsed and final_response_content is None:
            # 将用户消息和助手消息添加到历史
            self.chat_history.append({"role": "user", "content": query})
            self.chat_history.append(message)
            final_response_content = llm_content  # 直接使用模型的第一轮回复

        return final_response_content

    # ... (chat_loop 和 cleanup 不变) ...
    async def chat_loop(self):
        print("\n🤖 本地 LLM + MCP 客户端已启动！输入 'quit' 退出")
        while True:
            try:
                query = input("\n你: ").strip()
                if not query:
                    continue
                if query.lower() == 'quit':
                    break
                response_text = await self.process_query(query)
                print(f"\n🤖 Assistant: {response_text}")
            except KeyboardInterrupt:
                print("\n检测到中断，正在退出...")
                break
            except Exception as e:
                import traceback
                print(f"\n⚠️ 处理查询时发生严重错误: {str(e)}")
                print(traceback.format_exc())

    async def cleanup(self):
        print("正在关闭连接...")
        await self.exit_stack.aclose()
        print("连接已关闭。")


async def main():
    if len(sys.argv) < 2:
        # 现在 server_script_path 是必须的
        print("Usage: python client.py <path_to_mcp_server_script.py>")
        sys.exit(1)

    mcp_server_script = sys.argv[1]

    client = LocalMCPClient()
    try:
        # 必须先初始化 HTTP Session
        await client.initialize_http_session()
        # 连接到 MCP Server 以获取工具列表
        await client.connect_to_mcp_server(mcp_server_script)
        # 开始聊天循环
        await client.chat_loop()
    except FileNotFoundError as e:
        print(f"错误: {e}")
    except ValueError as e: # 捕获配置错误
         print(f"配置错误: {e}")
    except Exception as e: # 捕获其他启动时错误
         print(f"启动客户端时发生错误: {e}")
         import traceback
         print(traceback.format_exc())
    finally:
        await client.cleanup()


if __name__ == "__main__":
    # 运行示例: python client.py server.py
    asyncio.run(main())