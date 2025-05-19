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
import yaml

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

# 去重处理
group_links = list(set(raw_group_links))

# 匹配节点链接的正则表达式
url_pattern = re.compile(r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+|tuic://[^\s]+|hysteria://[^\s]+|hysteria2://[^\s]+)', re.IGNORECASE)

# ========== 节点解析函数 ==========
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

def parse_node(url, index):
    if url.lower().startswith("vmess://"):
        return parse_vmess_node(url, index)
    elif url.lower().startswith("ss://"):
        return parse_ss_node(url, index)
    elif url.lower().startswith("trojan://"):
        return parse_trojan_node(url, index)
    elif url.lower().startswith("vless://"):
        return parse_vless_node(url, index)
    elif url.lower().startswith("tuic://"):
        return parse_tuic_node(url, index)
    elif url.lower().startswith("hysteria://"):
        return parse_hysteria_node(url, index)
    elif url.lower().startswith("hysteria2://"):
        return parse_hysteria2_node(url, index)
    else:
        return None

# ========== 生成 Clash 配置文件 ==========
def generate_clash_yaml(nodes):
    # 生成 proxies 列表
    proxies = []
    for node in nodes:
        if node is None:
            continue
        proxy = None
        t = node.get("type")
        if t == "vmess":
            proxy = {
                "name": node["name"],
                "type": "vmess",
                "server": node["server"],
                "port": node["port"],
                "uuid": node["uuid"],
                "alterId": node.get("alterId", 0),
                "cipher": node.get("cipher", "auto"),
                "tls": node.get("tls", False),
                "udp": True,
            }
        elif t == "trojan":
            proxy = {
                "name": node["name"],
                "type": "trojan",
                "server": node["server"],
                "port": node["port"],
                "password": node["password"],
                "udp": node.get("udp", True),
                "skip-cert-verify": True,
            }
        elif t == "vless":
            proxy = {
                "name": node["name"],
                "type": "vless",
                "server": node["server"],
                "port": node["port"],
                "uuid": node["uuid"],
                "encryption": node.get("encryption", "none"),
                "udp": node.get("udp", True),
                "tls": False,
            }
        elif t == "ss":
            proxy = {
                "name": node["name"],
                "type": "ss",
                "server": node["server"],
                "port": node["port"],
                "cipher": node["cipher"],
                "password": node["password"],
                "udp": node.get("udp", True),
            }
        elif t == "tuic":
            proxy = {
                "name": node["name"],
                "type": "tuic",
                "server": node["server"],
                "port": node["port"],
                "password": node["password"],
                "udp": node.get("udp", True),
            }
        elif t == "hysteria":
            proxy = {
                "name": node["name"],
                "type": "hysteria",
                "server": node["server"],
                "port": node["port"],
                "password": node["password"],
                "udp": node.get("udp", True),
            }
        elif t == "hysteria2":
            proxy = {
                "name": node["name"],
                "type": "hysteria2",
                "server": node["server"],
                "port": node["port"],
                "password": node["password"],
                "udp": node.get("udp", True),
            }
        if proxy:
            proxies.append(proxy)

    # proxy-groups 例子
    proxy_group = {
        "name": "Auto",
        "type": "select",
        "proxies": [p["name Exception as e:
        logging.debug(f"解析 tuic 失败: {e}")
        return None

def parse_hysteria_node(url, index):
    # 简单示例，需根据实际 hysteria 协议补充
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

def parse_node(link, index):
    link = link.strip()
    if link.startswith("vmess://"):
        return parse_vmess_node(link, index)
    elif link.startswith("ss://"):
        return parse_ss_node(link, index)
    elif link.startswith("trojan://"):
        return parse_trojan_node(link, index)
    elif link.startswith("vless://"):
        return parse_vless_node(link, index)
    elif link.startswith("tuic://"):
        return parse_tuic_node(link, index)
    elif link.startswith("hysteria://"):
        return parse_hysteria_node(link, index)
    else:
        return None

# ========== Telegram 登录和抓取 ==========
async def fetch_messages(client, channel_username, limit=200):
    all_links = []
    offset_id = 0
    total_messages = 0
    while True:
        history = await client(GetHistoryRequest(
            peer=channel_username,
            offset_id=offset_id,
            offset_date=None,
            add_offset=0,
            limit=limit,
            max_id=0,
            min_id=0,
            hash=0
        ))
        if not history.messages:
            break
        total_messages += len(history.messages)
        for message in history.messages:
            if hasattr(message, "message") and message.message:
                found_links = url_pattern.findall(message.message)
                all_links.extend(found_links)
        offset_id = history.messages[-1].id
        # 限制抓取最近7天消息
        if history.messages[-1].date < datetime.now(timezone.utc) - timedelta(days=7):
            break
    logging.info(f"从频道 {channel_username} 抓取消息数: {total_messages}, 链接数: {len(all_links)}")
    return list(set(all_links))  # 去重

async def main():
    client = TelegramClient(session_file_path, api_id, api_hash)
    await client.start()
    all_nodes = []
    index = 0

    for group_url in group_links:
        group_username = group_url.split("t.me/")[-1].strip("/")
        logging.info(f"开始抓取 {group_username}")
        try:
            nodes = await fetch_messages(client, group_username)
            for node in nodes:
                index += 1
                parsed = parse_node(node, index)
                if parsed:
                    all_nodes.append(parsed)
        except Exception as e:
            logging.warning(f"抓取 {group_username} 失败: {e}")

    if not all_nodes:
        logging.warning("未抓取到任何节点，退出。")
        return

    # 构造 Clash 配置
    clash_conf = {
        "port": 7890,
        "socks-port": 7891,
        "allow-lan": False,
        "mode": "Rule",
        "log-level": "info",
        "proxies": all_nodes,
        "proxy-groups": [
            {
                "name": "自动选择",
                "type": "select",
                "proxies": [node["name"] for node in all_nodes]
            },
            {
                "name": "代理节点",
                "type": "fallback",
                "proxies": [node["name"] for node in all_nodes],
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300
            },
            {
                "name": "直连",
                "type": "direct",
            },
            {
                "name": "全球直连",
                "type": "direct",
            },
            {
                "name": "拒绝访问",
                "type": "reject",
            }
        ],
        "rules": [
            "DOMAIN-SUFFIX,google.com,自动选择",
            "DOMAIN-SUFFIX,youtube.com,自动选择",
            "DOMAIN-KEYWORD,google,自动选择",
            "DOMAIN-KEYWORD,youtube,自动选择",
            "GEOIP,CN,直连",
            "MATCH,自动选择"
        ]
    }

    # 保存 Clash 配置文件
    with open("clash", "w", encoding="utf-8") as f:
        yaml.dump(clash_conf, f, allow_unicode=True)
    logging.info(f"已生成 Clash 配置文件：clash")

if __name__ == "__main__":
    asyncio.run(main())
