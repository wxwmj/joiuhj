import os
import base64
import logging
import json
import re
import asyncio
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
import yaml

# ======== 配置部分 ========
API_ID_STR = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_B64 = os.getenv("SESSION_B64")

if not all([API_ID_STR, API_HASH, SESSION_B64]):
    raise ValueError("缺少环境变量 API_ID、API_HASH 或 SESSION_B64，请设置后再运行")

API_ID = int(API_ID_STR)

# 将 base64 编码的 session 解码为本地文件，供 Telethon 使用
SESSION_FILE = "session.session"
with open(SESSION_FILE, "wb") as f:
    f.write(base64.b64decode(SESSION_B64))

# Telegram 群组链接列表（你可以替换为你想抓取的群组）
GROUP_LINKS = list(set([
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
]))

# 节点链接匹配正则
NODE_PATTERN = re.compile(
    r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+|tuic://[^\s]+|hysteria://[^\s]+|hysteria2://[^\s]+)',
    re.IGNORECASE
)

# ======= 节点解析函数 =========
def parse_vmess(node: str, idx: int):
    try:
        b64_str = node[8:]
        # 补齐base64缺失的等号
        missing_padding = len(b64_str) % 4
        if missing_padding != 0:
            b64_str += "=" * (4 - missing_padding)
        decoded = base64.b64decode(b64_str).decode()
        conf = json.loads(decoded)
        return {
            "name": f"vmess_{idx}",
            "type": "vmess",
            "server": conf["add"],
            "port": int(conf["port"]),
            "uuid": conf["id"],
            "alterId": int(conf.get("aid", 0)),
            "cipher": "auto",
            "tls": conf.get("tls", "") == "tls",
            "network": conf.get("net", "tcp"),
        }
    except Exception as e:
        logging.debug(f"vmess解析失败: {e}")
        return None

def parse_trojan(node: str, idx: int):
    try:
        # trojan://password@host:port?params
        url = node[9:]
        password, rest = url.split("@", 1)
        hostport = rest.split("?", 1)[0]
        host, port = hostport.split(":")
        return {
            "name": f"trojan_{idx}",
            "type": "trojan",
            "server": host,
            "port": int(port),
            "password": password,
            "udp": True
        }
    except Exception as e:
        logging.debug(f"trojan解析失败: {e}")
        return None

def parse_vless(node: str, idx: int):
    try:
        # vless://uuid@host:port?params
        url = node[8:]
        uuid, rest = url.split("@", 1)
        hostport = rest.split("?", 1)[0]
        host, port = hostport.split(":")
        return {
            "name": f"vless_{idx}",
            "type": "vless",
            "server": host,
            "port": int(port),
            "uuid": uuid,
            "encryption": "none",
            "udp": True
        }
    except Exception as e:
        logging.debug(f"vless解析失败: {e}")
        return None

def parse_ss(node: str, idx: int):
    try:
        # ss://base64(method:password)@host:port 或 ss://base64(method:password@host:port)
        ss_uri = node[5:]
        # 先处理可能带有#注释，去除
        ss_uri = ss_uri.split("#")[0]
        if "@" in ss_uri:
            # 形如 base64(method:password)@host:port
            method_pass_b64, server = ss_uri.split("@", 1)
            # base64 decode
            missing_padding = len(method_pass_b64) % 4
            if missing_padding != 0:
                method_pass_b64 += "=" * (4 - missing_padding)
            method_pass = base64.b64decode(method_pass_b64).decode()
            method, password = method_pass.split(":")
            host, port = server.split(":")
        else:
            # 形如 base64(method:password@host:port)
            missing_padding = len(ss_uri) % 4
            if missing_padding != 0:
                ss_uri += "=" * (4 - missing_padding)
            decoded = base64.b64decode(ss_uri).decode()
            method_pass, server = decoded.split("@", 1)
            method, password = method_pass.split(":")
            host, port = server.split(":")
        return {
            "name": f"ss_{idx}",
            "type": "ss",
            "server": host,
            "port": int(port),
            "cipher": method,
            "password": password,
            "udp": True
        }
    except Exception as e:
        logging.debug(f"ss解析失败: {e}")
        return None

def parse_tuic(node: str, idx: int):
    try:
        url = node[6:]
        password, rest = url.split("@", 1)
        host, port = rest.split(":")
        return {
            "name": f"tuic_{idx}",
            "type": "tuic",
            "server": host,
            "port": int(port),
            "password": password,
            "udp": True
        }
    except Exception as e:
        logging.debug(f"tuic解析失败: {e}")
        return None

def parse_hysteria(node: str, idx: int):
    try:
        url = node[10:]
        password, rest = url.split("@", 1)
        host, port = rest.split(":")
        return {
            "name": f"hysteria_{idx}",
            "type": "hysteria",
            "server": host,
            "port": int(port),
            "password": password,
            "udp": True
        }
    except Exception as e:
        logging.debug(f"hysteria解析失败: {e}")
        return None

def parse_node(node: str, idx: int):
    node = node.strip()
    if node.startswith("vmess://"):
        return parse_vmess(node, idx)
    if node.startswith("ss://"):
        return parse_ss(node, idx)
    if node.startswith("trojan://"):
        return parse_trojan(node, idx)
    if node.startswith("vless://"):
        return parse_vless(node, idx)
    if node.startswith("tuic://"):
        return parse_tuic(node, idx)
    if node.startswith("hysteria://"):
        return parse_hysteria(node, idx)
    # hysteria2暂时不处理或同hysteria
    return None

# ========== Telegram 抓取消息 ==========
async def fetch_messages(client, channel_username, limit=200):
    all_links = []
    offset_id = 0
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
        for msg in history.messages:
            if hasattr(msg, "message") and msg.message:
                found = NODE_PATTERN.findall(msg.message)
                all_links.extend(found)
        offset_id = history.messages[-1].id
        # 只抓取最近7天消息
        if history.messages[-1].date < datetime.now(timezone.utc) - timedelta(days=7):
            break
    return list(set(all_links))

# ========== 主程序 ==========
async def main():
    logging.info("开始登录 Telegram 客户端...")
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.start()
    all_nodes = []
    idx = 0

    for url in GROUP_LINKS:
        username = url.split("t.me/")[-1].strip("/")
        logging.info(f"开始抓取频道: {username}")
        try:
            links = await fetch_messages(client, username)
            logging.info(f"抓取到 {len(links)} 条节点链接")
            for link in links:
                idx += 1
                node = parse_node(link, idx)
                if node:
                    all_nodes.append(node)
        except Exception as e:
            logging.warning(f"抓取频道 {username} 失败
