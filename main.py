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
from tempfile import NamedTemporaryFile
from dotenv import load_dotenv

# ========== 配置 ==========
load_dotenv()  # 加载 .env 配置文件

api_id_str = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
session_b64 = os.getenv("SESSION_B64")

if not all([api_id_str, api_hash, session_b64]):
    raise ValueError("❌ 缺少环境变量：API_ID、API_HASH 或 SESSION_B64")

api_id = int(api_id_str)

# Decode SESSION_B64 to get the actual session binary data
with NamedTemporaryFile(delete=False) as session_file:
    session_file.write(base64.b64decode(session_b64))
    session_file_path = session_file.name

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

# 匹配链接的正则表达式
url_pattern = re.compile(r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+|tuic://[^\s]+|hysteria://[^\s]+|hysteria2://[^\s]+)', re.IGNORECASE)

# ========== 统一节点解析函数 ==========
NODE_PARSERS = {
    "vmess://": lambda node, idx: parse_vmess_node(node, idx),
    "ss://": lambda node, idx: parse_ss_node(node, idx),
    "trojan://": lambda node, idx: parse_trojan_node(node, idx),
    "vless://": lambda node, idx: parse_vless_node(node, idx),
    "tuic://": lambda node, idx: parse_tuic_node(node, idx),
    "hysteria://": lambda node, idx: parse_hysteria_node(node, idx),
    "hysteria2://": lambda node, idx: parse_hysteria2_node(node, idx),
}

def parse_node(url, index):
    for protocol, parser in NODE_PARSERS.items():
        if url.startswith(protocol):
            return parser(url, index)
    return None

def parse_vmess_node(url, index):
    try:
        raw = base64.b64decode(url[8:])
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

        now = datetime.now(timezone.utc)
        all_links = set()

        # 设置时间范围循环：从1小时到24小时
        time_ranges = [1, 3, 6, 12, 24]  # 时间范围，单位为小时
        for hours in time_ranges:
            logging.info(f"📅 设置抓取时间范围: 最近 {hours} 小时")
            since = now - timedelta(hours=hours)
            group_stats.clear()  # 清除之前的统计数据

            # 并发抓取每个群组的消息
            results = await fetch_all_messages_with_rate_limit(client, group_links)

            # 如果没有符合要求的节点，进入下一个时间范围
            any_valid_node = False

            for link, messages in results:
                group_stats[link] = {"success": 0, "failed": 0}  # 初始化每个群组的统计

                for message in messages:
                    if message.date < since:
                        continue
                    found = url_pattern.findall(message.message or '')
                    all_links.update(found)

                    # 统计成功的节点
                    for idx, node in enumerate(found):
                        if parse_node(node, idx):
                            group_stats[link]["success"] += 1
                        else:
                            group_stats[link]["failed"] += 1

            if group_stats and any(stats["success"] > 0 for stats in group_stats.values()):
                any_valid_node = True  # 如果有符合要求的节点，停止调整时间范围
                break  # 退出循环，抓取已完成

        if not any_valid_node:
            logging.error("没有抓取到符合要求的节点，请检查群组配置或网络连接。")
            return  # 如果没有符合要求的节点，停止脚本执行

        logging.info(f"🔗 抓取完成，共抓取 {len(all_links)} 个节点")
        unique_nodes = list(set(all_links))

        # 仅生成 sub 文件
        await generate_subscribe_file(unique_nodes)

        logging.info(f"💾 保存节点配置完成，节点数：{len(unique_nodes)}")

        # 输出群组统计信息
        logging.info("📊 抓取统计:")
        for group_link, stats in group_stats.items():
            logging.info(f"{group_link}: 成功 {stats['success']}，失败 {stats['failed']}")

    except Exception as e:
        logging.error(f"🛑 登录失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
