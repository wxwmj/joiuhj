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
from telethon.tl.types import DocumentAttributeFilename
import docx

# ========== 配置 ==========
api_id_str = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
session_b64 = os.getenv("SESSION_B64")

if not all([api_id_str, api_hash, session_b64]):
    raise ValueError("❌ 缺少环境变量：API_ID、API_HASH 或 SESSION_B64")

api_id = int(api_id_str)
session_file_path = "session.session"
with open(session_file_path, "wb") as session_file:
    session_file.write(base64.b64decode(session_b64))

# ========== 日志 ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()]
)

# 群组链接（去重）
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
    'https://t.me/freevpnatm',
    'https://t.me/GetConfigIR',
    'https://t.me/VIPV2rayNGNP',
    'https://t.me/Outline_ir',
    'https://t.me/Farah_VPN',
    'https://t.me/sorenab1',
    'https://t.me/wxgmrjdcc',
]
group_links = []
seen = set()
for link in raw_group_links:
    if link not in seen:
        group_links.append(link)
        seen.add(link)
    else:
        logging.warning(f"重复群组链接已忽略：{link}")

# 节点正则
url_pattern = re.compile(r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+|tuic://[^\s]+|hysteria://[^\s]+|hysteria2://[^\s]+)', re.IGNORECASE)

# ========== 解析节点（省略原有详细解析函数，保留原逻辑） ==========
def parse_vmess_node(node, index):
    try:
        raw = base64.b64decode(node[8:])
        if not raw:
            return None
        conf = json.loads(raw)
        return {"name": f"vmess_{index}", "type": "vmess", "server": conf["add"], "port": int(conf["port"]), "uuid": conf["id"]}
    except:
        return None

def parse_trojan_node(url, index):
    try:
        raw = url[9:].split("@")
        host, port = raw[1].split("?")[0].split(":")
        return {"name": f"trojan_{index}", "type": "trojan", "server": host, "port": int(port)}
    except:
        return None

def parse_vless_node(url, index):
    try:
        raw = url[8:].split("@")
        host, port = raw[1].split("?")[0].split(":")
        return {"name": f"vless_{index}", "type": "vless", "server": host, "port": int(port)}
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
        return {"name": f"ss_{index}", "type": "ss", "server": server, "port": int(port)}
    except:
        return None

# ========== 文件抓取并解析 ==========
async def fetch_nodes_from_files(client, entity, since_time):
    nodes = set()
    try:
        files = await client.get_messages(entity, limit=30)  # 最近 30 条
        for msg in files:
            if not msg.file or msg.date < since_time:
                continue
            if msg.file.name and msg.file.name.lower().endswith(('.txt', '.docx', '.doc', '.csv')):
                path = await msg.download_media()
                logging.info(f"📥 下载文件: {path}")
                try:
                    content = ""
                    if path.endswith((".txt", ".csv")):
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                    elif path.endswith(".docx"):
                        doc = docx.Document(path)
                        content = "\n".join([p.text for p in doc.paragraphs])
                    elif path.endswith(".doc"):
                        logging.warning("⚠ 暂不支持直接解析 .doc，请手动转换")
                        continue
                    found_links = url_pattern.findall(content)
                    if found_links:
                        nodes.update(found_links)
                        logging.info(f"📄 文件 {path} 提取到 {len(found_links)} 个节点")
                except Exception as e:
                    logging.error(f"解析文件失败: {e}")
    except Exception as e:
        logging.error(f"获取文件消息失败: {e}")
    return nodes

# ========== 消息抓取 ==========
async def fetch_messages_for_group(client, link, since_time):
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
        text_nodes = set()
        for message in history.messages:
            if message.date < since_time:
                continue
            found = url_pattern.findall(message.message or '')
            text_nodes.update(found)

        file_nodes = set()
        if not text_nodes:
            logging.info(f"🔍 {link} 正文未找到节点，尝试抓取文件...")
            file_nodes = await fetch_nodes_from_files(client, entity, since_time)
            text_nodes.update(file_nodes)

        return link, text_nodes, file_nodes
    except Exception as e:
        logging.error(f"抓取 {link} 消息失败: {e}")
        return link, set(), set()

# ========== 生成订阅 ==========
async def generate_subscribe_file(nodes):
    try:
        joined_nodes = "\n".join(nodes)
        encoded = base64.b64encode(joined_nodes.encode()).decode()
        with open("sub", "w", encoding="utf-8") as f:
            f.write(encoded)
        logging.info("🎉 订阅文件生成完毕")
    except Exception as e:
        logging.error(f"生成订阅失败: {e}")

# ========== 主函数 ==========
async def main():
    logging.info("🚀 开始抓取 Telegram 节点")
    client = TelegramClient(session_file_path, api_id, api_hash)
    try:
        await client.start()
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=1)  # 只抓取当前一天的消息和文件
        results = await asyncio.gather(
            *[fetch_messages_for_group(client, link, since) for link in group_links]
        )

        all_links = set()
        for link, nodes, file_nodes in results:
            all_links.update(nodes)
            logging.info(f"🔗 {link} - 消息节点数量: {len(nodes)}，文件节点数量: {len(file_nodes)}")
        
        if not all_links:
            logging.error("❌ 没有抓取到符合要求的节点")
            return

        logging.info(f"🔗 抓取完成，共 {len(all_links)} 个节点")
        await generate_subscribe_file(list(all_links))
    except Exception as e:
        logging.error(f"🛑 脚本错误: {e}")

if __name__ == "__main__":
    asyncio.run(main())
