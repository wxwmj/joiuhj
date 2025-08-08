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
from telethon.tl.functions.messages import GetMessages

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
    'https://t.me/freevpnatm',
    'https://t.me/GetConfigIR',
    'https://t.me/VIPV2rayNGNP',
    'https://t.me/wxgmrjdcc',
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

# ========== 解析文件内容 ==========
async def parse_file_for_nodes(file, link, index):
    try:
        # 下载文件
        file_path = await client.download_media(file, file.name)
        logging.info(f"下载文件: {file.name}")

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        # 从文件内容中提取符合条件的节点
        nodes = url_pattern.findall(content)
        valid_nodes = []
        for idx, node in enumerate(nodes):
            if parse_vmess_node(node, idx) or parse_trojan_node(node, idx) or parse_vless_node(node, idx) or parse_ss_node(node, idx) or parse_tuic_node(node, idx) or parse_hysteria_node(node, idx) or parse_hysteria2_node(node, idx):
                valid_nodes.append(node)
        
        # 返回符合条件的节点
        return valid_nodes
    except Exception as e:
        logging.error(f"处理文件 {file.name} 时出错: {e}")
        return []

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

        all_links = set()

        # 遍历历史消息，查找文本文件并提取节点
        for message in history.messages:
            if message.media and isinstance(message.media, DocumentAttributeFilename):
                file = message.media.document
                if file.mime_type.startswith("text/"):  # 仅处理文本文件
                    logging.info(f"发现文本文件: {file}")
                    # 解析文件中的节点
                    file_nodes = await parse_file_for_nodes(file, link, 0)
                    all_links.update(file_nodes)

            # 如果消息包含节点链接，则直接提取
            if message.text:
                found = url_pattern.findall(message.text)
                all_links.update(found)

        return link, all_links

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
                        if parse_vmess_node(node, idx) or parse_trojan_node(node, idx) or parse_vless_node(node, idx) or parse_ss_node(node, idx) or parse_tuic_node(node, idx) or parse_hysteria_node(node, idx) or parse_hysteria2_node(node, idx):
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
