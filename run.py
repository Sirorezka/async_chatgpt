from src import async_completion
import os
import asyncio

os.environ["OPENAI_API_KEY"] = "XXXXXXXX"
os.environ["OPENAI_API_BASE"] = "https://api.openai.com/v1"


def main():
    messages1 = [
        {"role": "system", "content": "You are a poet. Respond to the following"},
        {"role": "user", "content": "Hello World"},
    ]

    messages2 = [
        {"role": "system", "content": "You are a programmer. Respond to the following"},
        {"role": "user", "content": "Hello World"},
    ]

    messages3 = [
        {"role": "system", "content": "You are a programmer. Respond to the following"},
        {"role": "user", "content": "Hello World"},
    ]

    chats = [messages1, messages2, messages3]
    resp = asyncio.run(async_completion.multiple_completions(chats))
    print(resp)


if __name__ == "__main__":
    main()
