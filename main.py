import os
import base64
import logging
import json
import re  # Ensure re module is imported for regular expressions
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
    format='%(asctime)s [%(levelname)s] %(message)s',
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
    'https://t.me/VPN365R',
    'https://t.me/ConfigsHUB2',
    'https://t.me/free_outline_keys',
    'https://t.me/config_proxy',
   
]

# 去重处理，并记录重复项
group_links = []
seen = set()
for link in raw_group_links:
    if link not in seen:
        group_links.append(link)
        seen.add(link)
    else:
        logging.warning(f"[去重] 重复电报群链接已忽略：{link}")

# 匹配链接的正则表达式
url_pattern = re.compile(r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+)', re.IGNORECASE)

# 最大抓取时间范围（修改为6小时）
max_age = timedelta(hours=6)

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

# ========== 生成订阅文件 ==========
async def generate_subscribe_file(nodes):
    try:
        # 生成 base64 编码订阅
        joined_nodes = "\n".join(nodes)
        encoded = base64.b64encode(joined_nodes.encode()).decode()
        with open("sub", "w", encoding="utf-8") as f:
            f.write(encoded)
        logging.info("[写入完成] sub")
    except Exception as e:
        logging.warning(f"[错误] 生成 base64 订阅失败：{e}")

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
                logging.warning(f"[重试] 第{attempt + 1}次尝试失败: {e}，等待 {delay:.2f} 秒后重试。")
                await asyncio.sleep(delay)
            else:
                logging.error(f"[重试失败] 重试次数用尽，操作失败: {e}")
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
        logging.warning(f"[抓取失败] 获取 {link} 消息失败：{e}")
        return link, []

async def fetch_all_messages_with_rate_limit(client, group_links):
    tasks = [fetch_messages_for_group(client, link) for link in group_links]
    results = await asyncio.gather(*tasks)
    return results

# ========== 主函数 ==========
async def main():
    logging.info("[启动] 开始抓取 Telegram 节点")
    
    client = TelegramClient(session_file_path, api_id, api_hash)

    group_stats = {}  # 用于统计每个群组的结果

    try:
        # 启动客户端
        await client.start()

        now = datetime.now(timezone.utc)
        since = now - max_age
        all_links = set()

        # 并发抓取每个群组的消息
        results = await fetch_all_messages_with_rate_limit(client, group_links)

        for link, messages in results:
            group_stats[link] = {"success": 0, "failed": 0}  # 初始化每个群组的统计

            for message in messages:
                if message.date < since:
                    continue
                found = url_pattern.findall(message.message or '')
                all_links.update(found)

                # 统计成功的节点
                for idx, node in enumerate(found):
                    if parse_vmess_node(node, idx) or parse_trojan_node(node, idx) or parse_vless_node(node, idx) or parse_ss_node(node, idx):
                        group_stats[link]["success"] += 1
                    else:
                        group_stats[link]["failed"] += 1

        logging.info(f"[完成] 抓取链接数: {len(all_links)}")
        unique_nodes = list(set(all_links))

        # 仅生成 sub 文件
        await generate_subscribe_file(unique_nodes)

        logging.info(f"[完成] 保存节点配置，节点数：{len(unique_nodes)}")

        # 输出群组统计信息
        logging.info("\n[抓取统计信息]:")
        for group_link, stats in group_stats.items():
            logging.info(f"{group_link}: 成功节点数={stats['success']}, 失败节点数={stats['failed']}")

    except Exception as e:
        logging.error(f"登录失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
