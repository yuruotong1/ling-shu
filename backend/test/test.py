from openai import OpenAI

client = OpenAI(
    api_key="sk-platform-dev",
    base_url="http://localhost:8000/v1",
)

session_id = None
messages = []

# 第一轮：不带 session_id，后端会自动创建
messages.append({"role": "user", "content": "今天天气怎么样"})
response = client.chat.completions.create(
    model="智能客服",
    messages=messages,
)
reply = response.choices[0].message.content
print("Agent:", reply)
messages.append({"role": "assistant", "content": reply})

# 拿到后端分配的 session_id（ChatCompletion extra='allow'，可直接访问）
session_id = response.session_id
print("session_id:", session_id)

# 第二轮：带上同一个 session_id，后端会记为同一会话的新轮次
messages.append({"role": "user", "content": "我的账号余额是多少"})
response = client.chat.completions.create(
    model="智能客服",
    messages=messages,
    extra_body={"session_id": session_id} if session_id else {},
)
reply = response.choices[0].message.content
print("Agent:", reply)
messages.append({"role": "assistant", "content": reply})

# 第三轮：继续复用 session_id
messages.append({"role": "user", "content": "帮我查一下最近的交易记录"})
response = client.chat.completions.create(
    model="智能客服",
    messages=messages,
    extra_body={"session_id": session_id} if session_id else {},
)
reply = response.choices[0].message.content
print("Agent:", reply)
