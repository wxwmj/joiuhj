import os
import base64
import logging
import json
import re
import asyncio
import socket
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest

# ===== 环境变量读取 =====
api_id = int(os.getenv("API_ID", ""))
api_hash = os.getenv("API_HASH")
session_b64 = os.getenv("SESSION_B64")

if not all([api_id, api_hash, session_b64]):
    raise ValueError("❌ 缺少 API_ID、API_HASH 或 SESSION_B64")

session_path = "session.session"
with open(session_path, "wb") as f:
    f.write(base64.b64decode(session_b64))

# ===== 日志配置 =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()]
)

# ===== 配置项 =====
group_links = [
    "https://t.me/VPN365R", "https://t.me/ConfigsHUB2",
    "https://t.me/free_outline_keys", "https://t.me/config_proxy",
    "https://t.me/freenettir", "https://t.me/oneclickvpnkeys",
    "https://t.me/entryNET", "https://t.me/daily_configs"
]
group_usernames = list(set(link.rstrip("/").split("/")[-1] for link in group_links))  # 去重并提取用户名

url_pattern = re.compile(r"(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+)", re.IGNORECASE)
max_age = timedelta(hours=6)
timeout = 3  # TCP连接测试超时

# ===== 节点有效性检测 =====
def is_node_reachable(host, port):
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except:
        return False

def validate_node(node):
    try:
        if node.startswith("vmess://"):
            data = json.loads(base64.b64decode(node[8:] + "===").decode())
            return is_node_reachable(data["add"], data["port"])
        elif node.startswith("trojan://") or node.startswith("vless://"):
            h = node.split("@")[1].split("?")[0].split(":")
            return is_node_reachable(h[0], h[1])
        elif node.startswith("ss://"):
            raw = node[5:]
            if "@" in raw:
                server_part = raw.split("@")[1]
            else:
                decoded = base64.b64decode(raw + "===").decode()
                server_part = decoded.split("@")[1]
            host, port = server_part.split(":")
            return is_node_reachable(host, port)
        return False
    except:
        return False

# ===== 抓取 Telegram 链接 =====
async def fetch_links():
    client = TelegramClient(session_path, api_id, api_hash)
    await client.start()
    now = datetime.now(timezone.utc)
    since = now - max_age
    all_links = set()

    for username in group_usernames:
        try:
            entity = await client.get_entity(username)
            history = await client(GetHistoryRequest(peer=entity, limit=100, offset_date=since, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
            group_links = 0
            for msg in history.messages:
                if msg.date < since:
                    continue
                found = url_pattern.findall(msg.message or "")
                all_links.update(found)
                group_links += len(found)
            logging.info(f"📥 群组 {username} 抓取 {group_links} 条链接")
        except Exception as e:
            logging.warning(f"[跳过] 获取 {username} 失败：{e}")
    return list(all_links)

# ===== 主流程 =====
async def main():
    logging.info("🚀 开始抓取 Telegram 节点")
    raw_links = await fetch_links()
    raw_links = list(set(raw_links))  # 去重
    logging.info(f"🔗 抓取链接总数：{len(raw_links)}")

    valid_links = []
    stats = {"vmess": 0, "ss": 0, "trojan": 0, "vless": 0, "invalid": 0}

    for link in raw_links:
        if validate_node(link):
            valid_links.append(link)
            if link.startswith("vmess://"): stats["vmess"] += 1
            elif link.startswith("ss://"): stats["ss"] += 1
            elif link.startswith("trojan://"): stats["trojan"] += 1
            elif link.startswith("vless://"): stats["vless"] += 1
        else:
            stats["invalid"] += 1

    logging.info("✅ 有效节点统计：")
    logging.info(f"   vmess: {stats['vmess']}")
    logging.info(f"   ss: {stats['ss']}")
    logging.info(f"   trojan: {stats['trojan']}")
    logging.info(f"   vless: {stats['vless']}")
    logging.info(f"   无效节点: {stats['invalid']}")

    try:
        joined = "\n".join(valid_links)
        encoded = base64.b64encode(joined.encode()).decode()
        with open("sub", "w", encoding="utf-8") as f:
            f.write(encoded)
        logging.info("📄 已保存 base64 订阅文件 sub")
    except Exception as e:
        logging.error(f"[失败] 写入 sub 文件错误: {e}")

if __name__ == "__main__":
    asyncio.run(main())
