import os
import re
import asyncio
import base64
import logging
import json
import yaml
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest

# ========== 配置 ==========
api_id_str = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
phone_number = os.getenv("PHONE_NUMBER")

if not all([api_id_str, api_hash, phone_number]):
    raise ValueError("❌ 缺少环境变量：API_ID、API_HASH 或 PHONE_NUMBER")

api_id = int(api_id_str)

group_usernames = [
    'VPN365R', 'ConfigsHUB2', 'free_outline_keys',
    'config_proxy', 'freenettir', 'wxgmrjdcc', 'daily_configs'
]

url_pattern = re.compile(r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+)', re.IGNORECASE)
max_age = timedelta(hours=12)

# ========== 日志配置 ==========
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()]
)

# ========== 工具函数 ==========
def safe_b64decode(data):
    try:
        data += '=' * (-len(data) % 4)  # 填补 base64 padding
        return base64.b64decode(data).decode()
    except Exception:
        return ""

# ========== 解析节点 ==========
def parse_vmess_node(node, index):
    try:
        raw = safe_b64decode(node[8:])
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
        raw = url[5:].split("@")
        password = raw[0]
        host_port = raw[1].split("?")[0].split(":")
        if len(host_port) < 2:
            return None
        host, port = host_port[0], int(host_port[1])
        return {
            "name": f"ss_{index}",
            "type": "ss",
            "server": host,
            "port": port,
            "password": password,
            "method": "aes-256-gcm"
        }
    except Exception as e:
        logging.warning(f"[解析失败] ss：{e}")
        return None

# ========== 获取Telegram消息 ==========
async def fetch_telegram_nodes(client, group_username):
    group = await client.get_entity(group_username)
    all_nodes = []
    async for message in client.iter_messages(group):
        if message.date < datetime.now() - max_age:
            continue
        urls = url_pattern.findall(message.text)
        for idx, url in enumerate(urls):
            if "cn" not in url.lower():
                if url.startswith("vmess://"):
                    node = parse_vmess_node(url, idx)
                elif url.startswith("trojan://"):
                    node = parse_trojan_node(url, idx)
                elif url.startswith("vless://"):
                    node = parse_vless_node(url, idx)
                elif url.startswith("ss://"):
                    node = parse_ss_node(url, idx)
                if node:
                    all_nodes.append(node)
    return all_nodes

# ========== 生成配置 ==========
def generate_clash_config(nodes, output_dir="output"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    clash_config = {
        "proxies": nodes,
        "proxy-groups": [
            {"name": "Auto", "type": "select", "proxies": [node["name"] for node in nodes]}
        ]
    }
    with open(os.path.join(output_dir, "wxx.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(clash_config, f, default_flow_style=False, allow_unicode=True)

def generate_v2ray_config(nodes, output_dir="output"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    v2ray_config = {
        "inbounds": [{"port": 1080, "listen": "127.0.0.1", "protocol": "socks", "settings": {"auth": "noauth", "udp": True}}],
        "outbounds": [{"protocol": node["type"], "settings": {"vnext": [{"address": node["server"], "port": node["port"], "users": [{"id": node["uuid"], "alterId": node["alterId"] if "alterId" in node else 0, "security": node["cipher"]}] }]}} for node in nodes],
    }
    with open(os.path.join(output_dir, "wxx.json"), "w", encoding="utf-8") as f:
        json.dump(v2ray_config, f, ensure_ascii=False, indent=2)

# ========== 主程序 ==========
async def main():
    async with TelegramClient("session", api_id, api_hash) as client:
        all_nodes = []
        for group_username in group_usernames:
            nodes = await fetch_telegram_nodes(client, group_username)
            all_nodes.extend(nodes)

        # 生成配置
        generate_clash_config(all_nodes)
        generate_v2ray_config(all_nodes)

if __name__ == "__main__":
    asyncio.run(main())
