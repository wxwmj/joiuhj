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

# 原始群组链接（可含重复）
raw_group_links = [
    'https://t.me/VPN365R',
    'https://t.me/ConfigsHUB2',
    'https://t.me/free_outline_keys',
    'https://t.me/config_proxy',
    'https://t.me/freenettir',
    'https://t.me/oneclickvpnkeys',
    'https://t.me/entryNET',
    'https://t.me/daily_configs',
    'https://t.me/DailyV2RY',
]

# 去重处理，并记录重复项
group_links = []
seen = set()
for link in raw_group_links:
    if link not in seen:
        group_links.append(link)
        seen.add(link)
    else:
        logging.warning(f"重复群组链接已忽略：{link}")

# 匹配链接的正则表达式，仅匹配所需协议
url_pattern = re.compile(r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+|tuic://[^\s]+|hysteria://[^\s]+|hysteria2://[^\s]+)', re.IGNORECASE)

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
        logging.debug(f"解析 vmess 失败: {e}")
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
        logging.debug(f"解析 trojan 失败: {e}")
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
        logging.debug(f"解析 vless 失败: {e}")
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
        logging.debug(f"解析 ss 失败: {e}")
        return None

def parse_tuic_node(url, index):
    try:
        # Tuic 的解析逻辑假设与 trojan 相似，具体根据实际情况调整
        raw = url[6:].split("@")
        password = raw[0]
        host_port = raw[1].split(":")
        if len(host_port) < 2:
            return None
        host, port = host_port[0], int(host_port[1])
        return {
            "name": f"tuic_{index}",
            "type": "tuic",
            "server": host,
            "port": port,
            "password": password,
            "udp": True
        }
    except Exception as e:
        logging.debug(f"解析 tuic 失败: {e}")
        return None

def parse_hysteria_node(url, index):
    try:
        raw = url[11:].split("@")
        password = raw[0]
        host_port = raw[1].split(":")
        if len(host_port) < 2:
            return None
        host, port = host_port[0], int(host_port[1])
        return {
            "name": f"hysteria_{index}",
            "type": "hysteria",
            "server": host,
            "port": port,
            "password": password,
            "udp": True
        }
    except Exception as e:
        logging.debug(f"解析 hysteria 失败: {e}")
        return None

def parse_hysteria2_node(url, index):
    try:
        raw = url[12:].split("@")
        password = raw[0]
        host_port = raw[1].split(":")
        if len(host_port) < 2:
            return None
        host, port = host_port[0], int(host_port[1])
        return {
            "name": f"hysteria2_{index}",
            "type": "hysteria2",
            "server": host,
            "port": port,
            "password": password,
            "udp": True
        }
    except Exception as e:
        logging.debug(f"解析 hysteria2 失败: {e}")
        return None

# ========== 生成订阅文件 ==========
async def generate_subscribe_file(nodes):
    try:
        # 生成 base64 编码订阅
        joined_nodes = "\n".join(nodes)
        encoded = base64.b64encode(joined_nodes.encode()).decode()
        with open("sub", "w", encoding="utf-8") as f:
            f.write(encoded)
        logging.info("🎉 订阅文件生成完毕")
    except Exception as e:
        logging.error(f"生成订阅失败: {e}")

# ========== 主逻辑 ==========
async def main():
    # 创建 Telegram 客户端
    async with TelegramClient(session_file_path, api_id, api_hash) as client:
        nodes = []
        for group_link in group_links:
            try:
                # 获取群组的历史消息
                group = await client.get_entity(group_link)
                messages = await client(GetHistoryRequest(group.id, limit=100))

                for message in messages.messages:
                    # 查找符合的节点 URL
                    matches = url_pattern.findall(message.text)
                    for match in matches:
                        index = random.randint(1, 10000)
                        if match.startswith("vmess://"):
                            node = parse_vmess_node(match, index)
                        elif match.startswith("ss://"):
                            node = parse_ss_node(match, index)
                        elif match.startswith("trojan://"):
                            node = parse_trojan_node(match, index)
                        elif match.startswith("vless://"):
                            node = parse_vless_node(match, index)
                        elif match.startswith("tuic://"):
                            node = parse_tuic_node(match, index)
                        elif match.startswith("hysteria://"):
                            node = parse_hysteria_node(match, index)
                        elif match.startswith("hysteria2://"):
                            node = parse_hysteria2_node(match, index)

                        if node:
                            nodes.append(node)
            except Exception as e:
                logging.error(f"抓取群组 {group_link} 时出错: {e}")

        if nodes:
            await generate_subscribe_file([json.dumps(node) for node in nodes])
        else:
            logging.info("没有抓取到任何节点")

if __name__ == "__main__":
    asyncio.run(main())
