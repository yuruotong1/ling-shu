"""
本地测试脚本 —— 验证灵枢引擎是否正常工作。
运行前请先启动服务：uv run python main.py
"""

import json
from openai import OpenAI, APIError

BASE_URL = "http://localhost:5490/v1"
# api_key 随便填，鉴权由 config.toml 里的 upstream.api_key 处理
client = OpenAI(base_url=BASE_URL, api_key="test")


def test_list_agents():
    print("=" * 50)
    print("【测试】列出所有 Agent")
    models = client.models.list()
    agents = [m.id for m in models.data]
    if agents:
        print(f"  已加载的 agent: {agents}")
    else:
        print("  暂无 agent（~/.ling-shu/agents/ 目录为空）")
    return agents


def test_basic_completion(model: str):
    print("=" * 50)
    print(f"【测试】普通对话  model={model}")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "用一句话介绍你自己"}],
        )
        if response.choices:
            print(f"  {response.choices[0].message.content}")
        else:
            print(f"  [ERROR] 上游返回异常（无 choices），原始响应: {response}")
    except APIError as e:
        print(f"  [ERROR] {e.status_code} {e.message}")


def test_stream(model: str):
    print("=" * 50)
    print(f"【测试】流式输出  model={model}")
    try:
        print("  ", end="", flush=True)
        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "数字 1 到 5，每个数字单独一行"}],
            stream=True,
        )
        for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta.content
                if delta:
                    print(delta, end="", flush=True)
        print()
    except APIError as e:
        print(f"\n  [ERROR] {e.status_code} {e.message}")


def test_structured_output(model: str):
    print("=" * 50)
    print(f"【测试】结构化输出  model={model}")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "人工智能正在改变世界"}],
        )
        if not response.choices:
            print(f"  [ERROR] 上游返回异常（无 choices），原始响应: {response}")
            return
        content = response.choices[0].message.content
        data = json.loads(content)
        print(f"  原始内容:        {content}")
        print(f"  translation:     {data.get('translation')}")
        print(f"  source_language: {data.get('source_language')}")
    except json.JSONDecodeError:
        print(f"  [ERROR] 返回内容不是合法 JSON: {content}")
    except APIError as e:
        print(f"  [ERROR] {e.status_code} {e.message}")


def test_passthrough():
    """直接传真实模型名，验证透传模式。"""
    print("=" * 50)
    print("【测试】透传模式（直接用真实模型名）")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "say 'hello' only"}],
        )
        print(f"  {response.choices[0].message.content}")
    except APIError as e:
        print(f"  [ERROR] {e.status_code} {e.message}")


if __name__ == "__main__":
    agents = test_list_agents()

    model = agents[0] if agents else "deepseek-chat"
    test_basic_completion(model)
    test_stream(model)
    test_structured_output(model)
    test_passthrough()

    print("=" * 50)
    print("全部测试完成")
