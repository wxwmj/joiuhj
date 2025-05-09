import os
import base64
import logging
import json
import yaml
import re
import asyncio
import requests
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest

# ========== 配置 ==========
api_id_str = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
session_b64 = os.getenv("SESSION_B64")

if not all([api_id_str, api_hash, session_b64]):
    raise ValueError("\u274c \u7f3a\u5c11\u73af\u5883\u53d8\u91cf\uff1aAPI_ID\u3001API_HASH \u6216 SESSION_B64")

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

# Telegram 群组链接（更直观）
group_links = [
    'https://t.me/VPN365R', 'https://t.me/ConfigsHUB2', 'https://t.me/free_outline_keys',
    'https://t.me/config_proxy', 'https://t.me/freenettir', 'https://t.me/oneclickvpnkeys',
    'https://t.me/entryNET', 'https://t.me/daily_configs'
]

url_pattern = re.compile(r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+)', re.IGNORECASE)
short_link_pattern = re.compile(r'(https?://(?:t\.cn|bit\.ly|tinyurl\.com|goo\.gl)/[^\s]+)', re.IGNORECASE)

# 初始抓取时间范围
initial_max_age = timedelta(hours=12)

# ========== 节点解析 ==========
def parse_vmess_node(node, index):
    try:
        raw = base64.b64decode(node[8:] + '===').decode('utf-8')
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
        return {
            "name": f"trojan_{index}",
            "type": "trojan",
            "server": host_port[0],
            "port": int(host_port[1]),
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
        return {
            "name": f"vless_{index}",
            "type": "vless",
            "server": host_port[0],
            "port": int(host_port[1]),
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

# ========== 短链解析 ==========
def resolve_short_link(url):
    try:
        r = requests.get(url, timeout=5, allow_redirects=True)
        return r.url if r.status_code == 200 else url
    except Exception:
        return url

# ========== Clash 配置生成 ==========
def generate_clash_config(nodes):
    proxies = []
    count = {"vmess": 0, "ss": 0, "trojan": 0, "vless": 0, "invalid": 0}

    for i, node in enumerate(nodes):
        proxy = None
        if node.startswith("vmess://"):
            proxy = parse_vmess_node(node, i + 1)
            count["vmess"] += 1 if proxy else 0
        elif node.startswith("trojan://"):
            proxy = parse_trojan_node(node, i + 1)
            count["trojan"] += 1 if proxy else 0
        elif node.startswith("vless://"):
            proxy = parse_vless_node(node, i + 1)
            count["vless"] += 1 if proxy else 0
        elif node.startswith("ss://"):
            proxy = parse_ss_node(node, i + 1)
            count["ss"] += 1 if proxy else 0
        else:
            count["invalid"] += 1

        if proxy:
            proxies.append(proxy)

    config = {
        "proxies": proxies,
        "proxy-groups": [{
            "name": "auto",
            "type": "url-test",
            "proxies": [p["name"] for p in proxies],
            "url": "http://www.gstatic.com/generate_204",
            "interval": 300
        }],
        "rules": ["MATCH,auto"]
    }

    with open("sub", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)

    logging.info(f"\ud83d\udcc4 已保存 base64 订阅文件 sub")
    logging.info("\u2705 有效节点统计：")
    for k, v in count.items():
        logging.info(f"   {k}: {v}")

# ========== Telegram 抓取 ==========
async def fetch_messages(max_age):
    client = TelegramClient(session_file_path, api_id, api_hash)
    await client.start()

    now = datetime.now(timezone.utc)
    since = now - max_age
    all_links = set()
    total_messages = 0

    for link in group_links:
        username = link.split("/")[-1]
        try:
            entity = await client.get_entity(username)
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
            count = 0
            for message in history.messages:
                if message.date < since:
                    continue
                total_messages += 1
                text = message.message or ""
                for url in short_link_pattern.findall(text):
                    text = text.replace(url, resolve_short_link(url))
                found = url_pattern.findall(text)
                count += len(found)
                all_links.update(found)
            logging.info(f"\ud83d\udcc5 群组 {username} 抓取 {count} 条链接")
        except Exception as e:
            logging.warning(f"[错误] 获取 {username} 失败：{e}")

    logging.info(f"\ud83d\udd17 抓取链接总数：{len(all_links)}，处理消息数：{total_messages}")
    return list(all_links)

# ========== 主函数 ==========
async def main():
    logging.info("\ud83d\ude80 开始抓取 Telegram 节点")
    raw_nodes = await fetch_messages(initial_max_age)

    # 自动扩展时间范围（抓太少）
    if len(raw_nodes) < 5:
        logging.info("\u26a0\ufe0f 链接太少，尝试扩大抓取时间至 24 小时")
        raw_nodes = await fetch_messages(timedelta(hours=24))

    unique_nodes = list(set(raw_nodes))
    generate_clash_config(unique_nodes)

    try:
        joined_nodes = "\n".join(unique_nodes)
        encoded = base64.b64encode(joined_nodes.encode()).decode()
        with open("sub", "a", encoding="utf-8") as f:
            f.write("\n# Base64:\n" + encoded)
    except Exception as e:
        logging.warning(f"[错误] 生成 base64 订阅失败：{e}")

if __name__ == "__main__":
    asyncio.run(main())
