import os
import base64
import logging
import json
import yaml
import re
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
session_file_path = "session.session"
with open(session_file_path, "wb") as f:
    f.write(base64.b64decode(session_b64))

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()]
)

group_usernames = [
    'VPN365R', 'ConfigsHUB2', 'free_outline_keys',
    'config_proxy', 'freenettir', 'wxgmrjdcc', 'daily_configs'
]
url_pattern = re.compile(r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+)', re.IGNORECASE)
max_age = timedelta(hours=6)

cn_keywords = ["cn", "china", "中国", "🇨🇳", "阿里云", "腾讯", "移动", "电信", "联通", "cmcc", "unicom"]

# ========== 判断原始链接是否含 CN ==========
def is_cn_node_raw(link):
    return any(k in link.lower() for k in cn_keywords)

# ========== 节点解析 ==========
def parse_vmess_node(node, index):
    try:
        raw = base64.b64decode(node[8:] + '==')
        conf = json.loads(raw)
        return {
            "name": f"vmess_{index}",
            "type": "vmess",
            "server": conf["add"],
            "port": int(conf["port"]),
            "uuid": conf["id"],
            "alterId": int(conf.get("aid", 0)),
            "cipher": "auto",
            "tls": conf.get("tls", "none") == "tls"
        }
    except:
        return None

def parse_trojan_node(url, index):
    try:
        raw = url[9:].split("@")
        password = raw[0]
        host, port = raw[1].split("?")[0].split(":")
        return {
            "name": f"trojan_{index}",
            "type": "trojan",
            "server": host,
            "port": int(port),
            "password": password,
            "udp": True
        }
    except:
        return None

def parse_vless_node(url, index):
    try:
        raw = url[8:].split("@")
        uuid = raw[0]
        host, port = raw[1].split("?")[0].split(":")
        return {
            "name": f"vless_{index}",
            "type": "vless",
            "server": host,
            "port": int(port),
            "uuid": uuid,
            "encryption": "none",
            "udp": True
        }
    except:
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
    except:
        return None

# ========== Telegram 抓取 ==========
async def fetch_messages():
    client = TelegramClient(session_file_path, api_id, api_hash)
    await client.start()

    now = datetime.now(timezone.utc)
    since = now - max_age
    all_links = set()

    for username in group_usernames:
        try:
            entity = await client.get_entity(username)
            history = await client(GetHistoryRequest(
                peer=entity, limit=100, offset_date=None,
                offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0
            ))
            for message in history.messages:
                if message.date < since:
                    continue
                found = url_pattern.findall(message.message or '')
                all_links.update(found)
        except Exception as e:
            logging.warning(f"[跳过] {username}：{e}")

    await client.disconnect()
    return list(all_links)

# ========== 主函数 ==========
async def main():
    logging.info("[开始] 抓取 Telegram 节点")
    raw_nodes = await fetch_messages()

    # 原始过滤 + 去重
    filtered_nodes = [n for n in raw_nodes if not is_cn_node_raw(n)]
    unique_nodes = list(set(filtered_nodes))

    # 再解析并检查 server/name 中的 CN
    clash_nodes = []
    raw_result = []

    for i, node in enumerate(unique_nodes):
        if node.startswith("vmess://"):
            parsed = parse_vmess_node(node, i+1)
        elif node.startswith("trojan://"):
            parsed = parse_trojan_node(node, i+1)
        elif node.startswith("vless://"):
            parsed = parse_vless_node(node, i+1)
        elif node.startswith("ss://"):
            parsed = parse_ss_node(node, i+1)
        else:
            continue

        if parsed:
            content = f"{parsed.get('name','')} {parsed.get('server','')}".lower()
            if not any(k in content for k in cn_keywords):
                clash_nodes.append(parsed)
                raw_result.append(node)

    # 生成 Clash 文件
    config = {
        "proxies": clash_nodes,
        "proxy-groups": [{
            "name": "auto",
            "type": "url-test",
            "proxies": [p["name"] for p in clash_nodes],
            "url": "http://www.gstatic.com/generate_204",
            "interval": 300
        }],
        "rules": ["MATCH,auto"]
    }

    with open("wxx.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)

    with open("wxx.json", "w", encoding="utf-8") as f:
        json.dump(raw_result, f, indent=2, ensure_ascii=False)

    encoded = base64.b64encode("\n".join(raw_result).encode()).decode()
    with open("sub", "w", encoding="utf-8") as f:
        f.write(encoded)

    logging.info(f"[完成] 节点总数：{len(raw_result)}，已写入 wxx.yaml / wxx.json / sub")

if __name__ == "__main__":
    asyncio.run(main())
