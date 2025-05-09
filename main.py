import os
import base64
import logging
import json
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

# ========== 去重和注释重复链接的函数 ==========
def deduplicate_group_links(raw_links):
    seen = set()
    cleaned_links = []
    annotated_links = []

    for link in raw_links:
        if link in seen:
            annotated_links.append(f"# '{link}',  # 🚫 重复")
        else:
            seen.add(link)
            cleaned_links.append(link)
            annotated_links.append(f"'{link}',")

    # 输出注释化的完整链接列表（打印或保存）
    print("# ===== Telegram 群组链接（自动标注重复） =====")
    for line in annotated_links:
        print(line)

    logging.info(f"[校验] 群组链接唯一数: {len(cleaned_links)}")
    return cleaned_links

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

# ========== 抓取 Telegram 消息 ==========
async def fetch_messages():
    client = TelegramClient(session_file_path, api_id, api_hash)

    try:
        # 启动客户端
        await client.start()

        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=6)  # 最大抓取时间范围（修改为6小时）
        all_links = set()

        # 定义需要抓取的群组链接
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
            'https://t.me/VPN365R',
            'https://t.me/ConfigsHUB2',
            'https://t.me/free_outline_keys',
        ]

        # 调用去重函数
        group_links = deduplicate_group_links(raw_group_links)

        for link in group_links:
            try:
                entity = await client.get_entity(link)  # 使用群组链接获取实体
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
                    found = url_pattern.findall(message.message or '')
                    all_links.update(found)
            except Exception as e:
                logging.warning(f"[错误] 获取 {link} 失败：{e}")

        logging.info(f"[完成] 抓取链接数: {len(all_links)}")
        return list(all_links)
    except Exception as e:
        logging.error(f"登录失败: {e}")
        return []

# ========== 主函数 ==========
async def main():
    logging.info("[启动] 开始抓取 Telegram 节点")
    raw_nodes = await fetch_messages()
    unique_nodes = list(set(raw_nodes))

    # 仅生成 sub 文件
    await generate_subscribe_file(unique_nodes)

    logging.info(f"[完成] 保存节点配置，节点数：{len(unique_nodes)}")

if __name__ == "__main__":
    asyncio.run(main())
