import requests

# 远程服务器的地址和端口
host = "http://192.168.50.208:8000"  # 请将 <REMOTE_IP> 替换为您远程电脑的实际IP地址
model_name = "QwQ-32B-AWQ"
api_key = "mindo"  # 确保这是一个字符串

# 准备请求的数据
data = {
    "model": model_name,
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "可以介绍一下你自己吗"}
    ],
    "temperature": 0.7,
    "max_tokens": 128
}

# 设置请求头，包括 API 密钥
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# 发送请求
response = requests.post(f"{host}/v1/chat/completions", json=data, headers=headers)

# 检查响应
if response.status_code == 200:
    generated_text = response.json()["choices"][0]["message"]["content"]
    print("Generated Text:", generated_text)
else:
    print("Failed to get response from the model.")
    print("Response Status Code:", response.status_code)
    print("Response Content:", response.text)