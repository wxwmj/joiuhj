import os
from telethon import TelegramClient
import base64

# 获取环境变量
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
phone_number = os.getenv("PHONE_NUMBER")
bot_token = os.getenv("BOT_TOKEN")
session_b64 = os.getenv("SESSION_B64")

# 检查 SESSION_B64 是否存在，如果有则使用它恢复会话
if session_b64:
    # 解码 base64 字符串并恢复会话
    session_str = base64.b64decode(session_b64).decode('utf-8')
    client = TelegramClient('session', api_id, api_hash).start()
    client.session.set_data(session_str.encode('utf-8'))
elif bot_token:
    client = TelegramClient('session', api_id, api_hash).start(bot_token=bot_token)
elif phone_number:
    client = TelegramClient('session', api_id, api_hash).start(phone_number=phone_number)
else:
    raise ValueError("❌ 缺少环境变量：PHONE_NUMBER 或 BOT_TOKEN 或 SESSION_B64")

# 示例：抓取 Telegram 群组消息
async def fetch_messages():
    # 你可以在此处添加抓取消息的具体实现
    async for message in client.iter_messages('your_telegram_channel'):
        print(message.text)

async def main():
    await fetch_messages()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
