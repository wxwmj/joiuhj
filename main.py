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
import yaml  # 需要提前 pip install pyyaml

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

raw_group_links = [
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
]

# 去重
group_links = []
seen = set()
for link in raw_group_links:
    if link not in seen:
        group_links.append(link)
        seen.add(link)
    else:
        logging.warning(f"重复群组链接已忽略：{link}")

url_pattern = re.compile(r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+|tuic://[^\s]+|hysteria://[^\s]+|hysteria2://[^\s]+)', re.IGNORECASE)

# ========== 节点解析 ==========
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
        raw = url[10:].split("@")
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
        raw = url[11:].split("@")
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

# 统一解析接口
def parse_node_url(url, index):
    if url.startswith("vmess://"):
        return parse_vmess_node(url, index)
    if url.startswith("trojan://"):
        return parse_trojan_node(url, index)
    if url.startswith("vless://"):
        return parse_vless_node(url, index)
    if url.startswith("ss://"):
        return parse_ss_node(url, index)
    if url.startswith("tuic://"):
        return parse_tuic_node(url, index)
    if url.startswith("hysteria://"):
        return parse_hysteria_node(url, index)
    if url.startswith("hysteria2://"):
        return parse_hysteria2_node(url, index)
    return None

# ========== 生成 base64 订阅文件 ==========
async def generate_subscribe_file(nodes):
    try:
        joined_nodes = "\n".join(nodes)
        encoded = base64.b64encode(joined_nodes.encode()).decode()
        with open("sub", "w", encoding="utf-8") as f:
            f.write(encoded)
        logging.info("🎉 订阅文件生成完毕：sub")
    except Exception as e:
        logging.error(f"生成订阅失败: {e}")

# ========== 生成 Clash 配置文件 ==========
async def generate_clash_file(parsed_nodes):
    try:
        # 生成 Clash 配置格式
        proxies = []
        for node in parsed_nodes:
            if node is None:
                continue
            # 按类型生成对应格式，简单示例
            if node["type"] == "vmess":
                proxies.append({
                    "name": node["name"],
                    "type": "vmess",
                    "server": node["server"],
                    "port": node["port"],
                    "uuid": node["uuid"],
                    "alterId": node.get("alterId", 0),
                    "cipher": node.get("cipher", "auto"),
                    "tls": node.get("tls", False),
                })
            elif node["type"] == "trojan":
                proxies.append({
                    "name": node["name"],
                    "type": "trojan",
                    "server": node["server"],
                    "port": node["port"],
                    "password": node["password"],
                    "udp": node.get("udp", True)
                })
            elif node["type"] == "vless":
                proxies.append({
                    "name": node["name"],
                    "type": "vless",
                    "server": node["server"],
                    "port": node["port"],
                    "uuid": node["uuid"],
                    "encryption": node.get("encryption", "none"),
                    "udp": node.get("udp", True),
                })
            elif node["type"] == "ss":
                proxies.append({
                    "name": node["name"],
                    "type": "ss",
                    "server": node["server"],
                    "port": node["port"],
                    "cipher": node["cipher"],
                    "password": node["password"],
                    "udp": node.get("udp", True)
                })
            elif node["type"] == "tuic":
                proxies.append({
                    "name": node["name"],
                    "type": "tuic",
                    "server": node["server"],
                    "port": node["port"],
                    "password": node["password"],
                    "udp": node.get("udp", True)
                })
            elif node["type"] == "hysteria":
                proxies.append({
                    "name": node["name"],
                    "type": "hysteria",
                    "server": node["server"],
                    "port": node["port"],
                    "password": node["password"],
                    "udp": node.get("udp", True)
                })
            elif node["type"] == "hysteria2":
                proxies.append({
                    "name": node["name"],
                    "type": "hysteria2",
                    "server": node["server"],
                    "port": node["port"],
                    "password": node["password"],
                    "udp": node.get("udp", True)
                })

        clash_config = {
            "proxies": proxies,
            "proxy-groups": [
                {
                    "name": "自动选择",
                    "type": "select",
                    "proxies": [p["name"] for p in proxies]
                }
            ],
            "rules": [
                "MATCH, 自动选择"
            ]
        }

        with open("clash", "w", encoding="utf-8") as f:
            yaml.dump(clash_config, f, allow_unicode=True)
        logging.info("🎉 Clash 配置文件生成完毕：clash")
    except Exception as e:
        logging.error(f"生成 Clash 文件失败: {e}")

# ========== 主逻辑 ==========
async def main():
    client = TelegramClient(session_file_path, api_id, api_hash)
    await client.start()
    all_nodes = []

    start_time = datetime.now(timezone.utc) - timedelta(days=1)

    for group_link in group_links:
        try:
            entity = await client.get_entity(group_link)
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
                if message.date < start_time:
                    continue
                if not message.message:
                    continue
                urls = url_pattern.findall(message.message)
                all_nodes.extend(urls)
        except Exception as e:
            logging.error(f"获取群组消息失败 {group_link}: {e}")

    # 去重
    all_nodes = list(set(all_nodes))
    logging.info(f"抓取到节点数：{len(all_nodes)}")

    parsed_nodes = []
    for idx, node_url in enumerate(all_nodes, 1):
        parsed = parse_node_url(node_url, idx)
        if parsed:
            parsed_nodes.append(parsed)

    # 生成 base64 订阅文件
    await generate_subscribe_file(all_nodes)

    # 生成 clash 配置文件
    await generate_clash_file(parsed_nodes)

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
