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

# 去重处理，并记录重复项
group_links = []
seen = set()
for link in raw_group_links:
    if link not in seen:
        group_links.append(link)
        seen.add(link)
    else:
        logging.warning(f"重复群组链接已忽略：{link}")

# 匹配链接的正则表达式
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

# ========== 错误处理与重试机制 ==========
MAX_RETRIES = 3
RETRY_DELAY = 2  # 每次重试的延迟时间，单位秒

async def fetch_with_retries(fetch_function, *args, **kwargs):
    """添加重试机制，处理瞬时网络问题"""
    for attempt in range(MAX_RETRIES):
        try:
            return await fetch_function(*args, **kwargs)
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                delay = random.uniform(RETRY_DELAY, RETRY_DELAY * 2)  # 随机延迟
                logging.debug(f"第{attempt + 1}次重试失败: {e}，等待 {delay:.2f} 秒")
                await asyncio.sleep(delay)
            else:
                logging.error(f"重试失败: {e}")
                raise  # 如果重试用尽，抛出异常

# ========== 抓取 Telegram 消息 ==========
async def fetch_messages_for_group(client, link):
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
        return link, history.messages
    except Exception as e:
        logging.error(f"抓取 {link} 消息失败: {e}")
        return link, []

async def fetch_all_messages_with_rate_limit(client, group_links):
    tasks = [fetch_messages_for_group(client, link) for link in group_links]
    results = await asyncio.gather(*tasks)
    return results

# ========== 主函数 ==========
async def main():
    logging.info("🚀 开始抓取 Telegram 节点")
    
    client = TelegramClient(session_file_path, api_id, api_hash)
    
    group_stats = {}  # 用于统计每个群组的结果

    try:
        # 启动客户端
        await client.start()

        # 获取所有群组消息
        results = await fetch_all_messages_with_rate_limit(client, group_links)

        # 处理每个群组的结果
        for link, messages in results:
            nodes = []
            for index, message in enumerate(messages):
                if message.text:
                    matches = url_pattern.findall(message.text)
                    for match in matches:
                        if "vmess://" in match:
                            node = parse_vmess_node(match, index)
                        elif "ss://" in match:
                            node = parse_ss_node(match, index)
                        elif "trojan://" in match:
                            node = parse_trojan_node(match, index)
                        elif "vless://" in match:
                            node = parse_vless_node(match, index)
                        elif "tuic://" in match:
                            node = parse_tuic_node(match, index)
                        elif "hysteria://" in match:
                            node = parse_hysteria_node(match, index)
                        elif "hysteria2://" in match:
                            node = parse_hysteria2_node(match, index)
                        
                        if node:
                            nodes.append(node)
            
            group_stats[link] = len(nodes)
            logging.info(f"抓取到 {link} 的节点数：{len(nodes)}")

        # 生成订阅文件
        await generate_subscribe_file([json.dumps(node) for node in nodes])

    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
