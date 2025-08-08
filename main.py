import os
import base64
import logging
import json
import re
import asyncio
import random
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
    format='%(asctime)s - %(message)s',
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()]
)

# 匹配链接的正则表达式
url_pattern = re.compile(r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+|tuic://[^\s]+|hysteria://[^\s]+|hysteria2://[^\s]+)', re.IGNORECASE)

# ========== 解析节点 ==========
def parse_node(url, index, node_type):
    try:
        if node_type == 'vmess':
            raw = base64.b64decode(url[8:])
            conf = json.loads(raw)
            return {"name": f"vmess_{index}", "type": "vmess", "server": conf["add"], "port": int(conf["port"]), "uuid": conf["id"], "alterId": int(conf.get("aid", 0)), "cipher": "auto", "tls": conf.get("tls", "none") == "tls"}
        elif node_type == 'trojan':
            raw = url[9:].split("@")
            password, host_port = raw[0], raw[1].split(":")
            return {"name": f"trojan_{index}", "type": "trojan", "server": host_port[0], "port": int(host_port[1]), "password": password, "udp": True}
        elif node_type == 'vless':
            raw = url[8:].split("@")
            uuid, host_port = raw[0], raw[1].split(":")
            return {"name": f"vless_{index}", "type": "vless", "server": host_port[0], "port": int(host_port[1]), "uuid": uuid, "encryption": "none", "udp": True}
        elif node_type == 'ss':
            raw = base64.b64decode(url[5:] + '===').decode()
            method, password, server_port = raw.split(":")[0], raw.split(":")[1], raw.split("@")[1]
            return {"name": f"ss_{index}", "type": "ss", "server": server_port.split(":")[0], "port": int(server_port.split(":")[1]), "cipher": method, "password": password, "udp": True}
        elif node_type == 'tuic':
            raw = url[6:].split("@")
            password, host_port = raw[0], raw[1].split(":")
            return {"name": f"tuic_{index}", "type": "tuic", "server": host_port[0], "port": int(host_port[1]), "password": password, "udp": True}
        elif node_type == 'hysteria':
            raw = url[10:].split("@")
            password, host_port = raw[0], raw[1].split(":")
            return {"name": f"hysteria_{index}", "type": "hysteria", "server": host_port[0], "port": int(host_port[1]), "password": password, "udp": True}
        elif node_type == 'hysteria2':
            raw = url[11:].split("@")
            password, host_port = raw[0], raw[1].split(":")
            return {"name": f"hysteria2_{index}", "type": "hysteria2", "server": host_port[0], "port": int(host_port[1]), "password": password, "udp": True}
    except Exception as e:
        logging.debug(f"解析 {node_type} 失败: {e}")
        return None

# ========== 从文件中解析节点 ==========
def parse_nodes_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            found_urls = url_pattern.findall(content)
            return found_urls
    except Exception as e:
        logging.error(f"读取文件失败 {file_path}: {e}")
        return []

# ========== 抓取 Telegram 消息 ==========
async def fetch_messages_for_group(client, link, since):
    try:
        entity = await client.get_entity(link)
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
        messages = [msg.message for msg in history.messages if msg.date >= since]
        return link, messages
    except Exception as e:
        logging.error(f"抓取 {link} 消息失败: {e}")
        return link, []

async def fetch_all_messages(client, group_links, since):
    tasks = [fetch_messages_for_group(client, link, since) for link in group_links]
    results = await asyncio.gather(*tasks)
    all_links = set()
    for link, messages in results:
        for message in messages:
            found = url_pattern.findall(message)
            all_links.update(found)
    return all_links

# ========== 主函数 ==========
async def main():
    logging.info("🚀 开始抓取 Telegram 节点")
    
    client = TelegramClient(session_file_path, api_id, api_hash)
    
    group_links = [
        'https://t.me/ConfigsHUB2',
    'https://t.me/config_proxy',
    'https://t.me/free_outline_keys',
    'https://t.me/freenettir',
    'https://t.me/v2ray_configs_pool',
    'https://t.me/VPN365R',
    'https://t.me/DailyV2RY',
    'https://t.me/Trick_mobil',
    'https://t.me/vpnplusee_free',
    'https://t.me/daily_configs',
    'https://t.me/oneclickvpnkeys',
    'https://t.me/V2All',
    'https://t.me/Outline_FreeKey',
    'https://t.me/V2ranNG_vpn',
    'https://t.me/v2rey_grum',
    'https://t.me/freevpnatm',
    'https://t.me/GetConfigIR',
    'https://t.me/VIPV2rayNGNP',
    'https://t.me/wxgmrjdcc',
    ]
    file_paths = ["path/to/your/file1.txt", "path/to/your/file2.txt"]

    try:
        # 启动客户端
        await client.start()

        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=3)

        # 抓取 Telegram 消息
        all_links = await fetch_all_messages(client, group_links, since)

        # 如果没有抓到节点，尝试从文件提取
        if not all_links:
            logging.info("Telegram 抓取不到节点，尝试从文件中提取")
            for file_path in file_paths:
                found_in_file = parse_nodes_from_file(file_path)
                all_links.update(found_in_file)

        if not all_links:
            logging.error("没有抓取到有效节点")
            return

        logging.info(f"🔗 抓取完成，共抓取 {len(all_links)} 个节点")
        unique_nodes = list(set(all_links))

        # 生成订阅文件
        await generate_subscribe_file(unique_nodes)

        logging.info(f"💾 保存节点配置完成，节点数：{len(unique_nodes)}")

    except Exception as e:
        logging.error(f"🛑 登录失败: {e}")

# ========== 生成订阅文件 ==========
async def generate_subscribe_file(nodes):
    try:
        joined_nodes = "\n".join(nodes)
        encoded = base64.b64encode(joined_nodes.encode()).decode()
        with open("sub", "w", encoding="utf-8") as f:
            f.write(encoded)
        logging.info("🎉 订阅文件生成完毕")
    except Exception as e:
        logging.error(f"生成订阅失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
