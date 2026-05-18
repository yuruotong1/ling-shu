from openai import OpenAI

client = OpenAI(
    api_key="sk-platform-dev",
    base_url="http://localhost:8000/v1",
)

response = client.chat.completions.create(
    model="test4",
    messages=[{"role": "user", "content": "今天天气怎么样呀！！！"}],
)

print(response.choices[0].message.content)