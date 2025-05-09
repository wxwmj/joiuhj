import os
import base64
import logging
import json
import yaml
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

# 需要抓取的 Telegram 群链接（更改为链接形式）
group_links = [
    'https://t.me/VPN365R',
    'https://t.me/ConfigsHUB2',
    'https://t.me/free_outline_keys',
    'https://t.me/config_proxy',
    'https://t.me/freenettir',
    'https://t.me/oneclickvpnkeys',
    'https://t.me/entryNET',
    'https://t.me/daily_configs'
]

# 匹配链接的正则表达式
url_pattern = re.compile(r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+)', re.IGNORECASE)

# 最大抓取时间范围（修改为6小时）
max_age = timedelta(hours=6)

# ========== 节点有效性测试 ==========
def is_valid_node(proxy):
    if not proxy:
        return False
    required_fields = ["server", "port"]
    return all(k in proxy and proxy[k] for k in required_fields)

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

# ========== 生成 Clash 配置 ==========
def generate_clash_config(nodes):
    proxies = []

    for i, node in enumerate(nodes):
        proxy = None
        if node.startswith("vmess://"):
            proxy = parse_vmess_node(node, i + 1)
        elif node.startswith("trojan://"):
            proxy = parse_trojan_node(node, i + 1)
        elif node.startswith("vless://"):
            proxy = parse_vless_node(node, i + 1)
        elif node.startswith("ss://"):
            proxy = parse_ss_node(node, i + 1)

        if is_valid_node(proxy):
            proxies.append(proxy)
        else:
            logging.warning(f"[无效节点] 已跳过：{node[:30]}...")

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

    with open("wxx.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)
    logging.info(f"[保存成功] wxx.yaml，共有效节点：{len(proxies)}")

# ========== 抓取 Telegram 消息 ==========
async def fetch_messages():
    client = TelegramClient(session_file_path, api_id, api_hash)
    await client.start()

    now = datetime.now(timezone.utc)
    since = now - max_age
    all_links = set()

    for link in group_links:
        try:
            logging.info(f"[开始] 抓取群组: {link}")
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
            count = 0
            for message in history.messages:
                if message.date < since:
                    continue
                found = url_pattern.findall(message.message or '')
                if found:
                    all_links.update(found)
                    count += len(found)
            logging.info(f"[完成] {link} 提取链接数：{count}")
        except Exception as e:
            logging.warning(f"[失败] 抓取群 {link} 失败：{type(e).__name__} - {e}")

    logging.info(f"[统计] 抓取总节点数：{len(all_links)}")
    return list(all_links)

# ========== 主函数 ==========
async def main():
    logging.info("[启动] 开始抓取 Telegram 节点")
    raw_nodes = await fetch_messages()
    unique_nodes = list(set(raw_nodes))

    # 保存抓取的节点
    with open("unique_nodes.txt", "w", encoding="utf-8") as f:
        for node in unique_nodes:
            f.write(node + "\n")

    generate_clash_config(unique_nodes)

    # 生成 base64 编码订阅文件 sub
    try:
        joined_nodes = "\n".join(unique_nodes)
        encoded = base64.b64encode(joined_nodes.encode()).decode()
        with open("sub", "w", encoding="utf-8") as f:
            f.write(encoded)
        logging.info("[保存成功] base64订阅文件：sub")
    except Exception as e:
        logging.error(f"[失败] 生成 sub 文件失败：{e}")

    logging.info(f"[完成] 保存节点配置，节点数：{len(unique_nodes)}")

if __name__ == "__main__":
    asyncio.run(main())
