import os
import base64
import logging
import json
import re  # Ensure re module is imported for regular expressions
import asyncio
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest

# ========== 配置 ==========
api_id_str = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
session_b64 = os.getenv("SESSION_B64")

if not all([api_id_str, api_hash, session_b64]):
    raise ValueError("❌ 缺少环境变量：API_ID、API_HASH 或 SESSION_B64")

api_id = int(api_id_str)

# Decode SESSION_B64 to get the actual session binary data
session_file_path = "session.session"
with open(session_file_path, "wb") as session_file:
    session_file.write(base64.b64decode(session_b64))

# ========== 日志配置 ==========
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()]
)

# 需要抓取的 Telegram 群组链接
group_links = [
    'https://t.me/VPN365R', 
    'https://t.me/ConfigsHUB2', 
    'https://t.me/free_outline_keys',
    'https://t.me/config_proxy', 
    'https://t.me/freenettir', 
    'https://t.me/oneclickvpnkeys', 
    'https://t.me/entryNET', 
    'https://t.me/daily_configs', 
    'https://t.me/VPN365R',  
    'https://t.me/ConfigsHUB2', 
]

# 在抓取之前对群组链接进行去重
group_links = list(set(group_links))
logging.info(f"[去重完成] 群组链接数: {len(group_links)}")

# 匹配链接的正则表达式
url_pattern = re.compile(r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+)', re.IGNORECASE)

# 最大抓取时间范围（修改为6小时）
max_age = timedelta(hours=6)

# ========== 解析节点 ==========
def parse_vmess_node(node, index):
    try:
        raw = base64.b64decode(node[8:])
        if not raw:
            return None
        conf = json.loads(raw)
        return {
            "name": f"vmess_{index}",
            "type": "vmess",
            "server": conf["add"],
            "port": int(conf["port"]),
            "uuid": conf["id"],
            "alterId": int(conf.get("aid", 0)),
            "cipher": "auto",
            "tls": conf.get("tls", "none") == "tls",
        }
    except Exception as e:
        logging.warning(f"[解析失败] vmess：{e}")
        return None

def parse_trojan_node(url, index):
    try:
        raw = url[9:].split("@")
        password = raw[0]
        host_port = raw[1].split("?")[0].split(":")
        if len(host_port) < 2:
            return None
        host, port = host_port[0], int(host_port[1])
        return {
            "name": f"trojan_{index}",
            "type": "trojan",
            "server": host,
            "port": port,
            "password": password,
            "udp": True
        }
    except Exception as e:
        logging.warning(f"[解析失败] trojan：{e}")
        return None

def parse_vless_node(url, index):
    try:
        raw = url[8:].split("@")
        uuid = raw[0]
        host_port = raw[1].split("?")[0].split(":")
        if len(host_port) < 2:
            return None
        host, port = host_port[0], int(host_port[1])
        return {
            "name": f"vless_{index}",
            "type": "vless",
            "server": host,
            "port": port,
            "uuid": uuid,
            "encryption": "none",
            "udp": True
        }
    except Exception as e:
        logging.warning(f"[解析失败] vless：{e}")
        return None

def parse_ss_node(url, index):
    try:
        raw = url[5:]
        if "#" in raw:
            raw = raw.split("#")[0]
        if "@" in raw:
            method_password, server_part = raw.split("@")
            method, password = base64.b64decode(method_password + '===').decode().split(":")
        else:
            decoded = base64.b64decode(raw + '===').decode()
            method_password, server_part = decoded.split("@")
            method, password = method_password.split(":")
        server, port = server_part.split(":")
        return {
            "name": f"ss_{index}",
            "type": "ss",
            "server": server,
            "port": int(port),
            "cipher": method,
            "password": password,
            "udp": True
        }
    except Exception as e:
        logging.warning(f"[解析失败] ss：{e}")
        return None

# ========== 生成订阅文件 ==========
async def generate_subscribe_file(nodes):
    try:
        # 生成 base64 编码订阅
        joined_nodes = "\n".join(nodes)
        encoded = base64.b64encode(joined_nodes.encode()).decode()
        with open("sub", "w", encoding="utf-8") as f:
            f.write(encoded)
        logging.info("[写入完成] sub")
    except Exception as e:
        logging.warning(f"[错误] 生成 base64 订阅失败：{e}")

# ========== 抓取 Telegram 消息 ==========
async def fetch_messages():
    client = TelegramClient(session_file_path, api_id, api_hash)

    try:
        # 启动客户端
        await client.start()

        now = datetime.now(timezone.utc)
        since = now - max_age
        all_links = set()  # 用于存储所有抓取到的链接

        for link in group_links:
            try:
                entity = await client.get_entity(link)  # 使用群组链接获取实体
                history = await client(GetHistoryRequest(
                    peer=entity,
                    limit=100,
                    offset_date=None,
                    offset_id=0,
                    max_id=0,
                    min_id=0,
                    add_offset=0,
                    hash=0
                ))
                for message in history.messages:
                    if message.date < since:
                        continue
                    found = url_pattern.findall(message.message or '')
                    all_links.update(found)  # 直接去重
            except Exception as e:
                logging.warning(f"[错误] 获取 {link} 失败：{e}")

        logging.info(f"[完成] 抓取链接数: {len(all_links)}")
        return list(all_links)  # 返回去重后的链接列表
    except Exception as e:
        logging.error(f"登录失败: {e}")
        return []

# ========== 主函数 ==========
async def main():
    logging.info("[启动] 开始抓取 Telegram 节点")
    raw_nodes = await fetch_messages()
    unique_nodes = list(set(raw_nodes))  # 再次去重

    # 仅生成 sub 文件
    await generate_subscribe_file(unique_nodes)

    logging.info(f"[完成] 保存节点配置，节点数：{len(unique_nodes)}")

if __name__ == "__main__":
    asyncio.run(main())
