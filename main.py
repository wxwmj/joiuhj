import os
import re
import base64
import logging
from datetime import datetime, timedelta, timezone
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
import asyncio

# 加载环境变量
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
session_b64 = os.getenv("SESSION_B64")
group_links = os.getenv("GROUP_LINKS", "").split(",")

session_file_path = "anon.session"

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 节点正则表达式
url_pattern = re.compile(r"(vmess|ss|trojan|vless|tuic|hysteria|hysteria2)://[\S]+")

# 节点解析函数们（此处略，保留原始的 parse_vmess_node 等）
def parse_vmess_node(url, index):
    try:
        data = base64.b64decode(url.split("//", 1)[1] + '==').decode('utf-8')
        return {"type": "vmess", "data": data}
    except:
        return None

# 其他 parse_xxx_node 略，保持你的原样
# ...

def parse_node(url, index):
    scheme = url.split("://")[0].lower()
    parsers = {
        "vmess": parse_vmess_node,
        "ss": parse_ss_node,
        "trojan": parse_trojan_node,
        "vless": parse_vless_node,
        "tuic": parse_tuic_node,
        "hysteria": parse_hysteria_node,
        "hysteria2": parse_hysteria2_node
    }
    parser = parsers.get(scheme)
    if parser:
        return parser(url, index)
    return None

async def fetch_all_messages_with_rate_limit(client, group_links):
    results = []
    for link in group_links:
        try:
            entity = await client.get_entity(link)
            messages = await client.get_messages(entity, limit=300)
            results.append((link, messages))
            await asyncio.sleep(1.5)
        except Exception as e:
            logging.warning(f"抓取 {link} 失败: {e}")
            results.append((link, []))
    return results

def decode_session(session_b64):
    try:
        raw_data = base64.b64decode(session_b64)
        with open(session_file_path, "wb") as f:
            f.write(raw_data)
        return True
    except Exception as e:
        logging.error(f"解码 session 失败: {e}")
        return False

async def generate_subscribe_file(nodes):
    content = "\n".join(nodes)
    encoded = base64.b64encode(content.encode()).decode()
    with open("sub", "w") as f:
        f.write(encoded)
    logging.info("写入 base64 订阅文件 sub")

async def main():
    logging.info("🚀 开始抓取 Telegram 节点")
    group_stats = {}
    protocol_stats = {}

    try:
        if not decode_session(session_b64):
            return

        async with TelegramClient(session_file_path, api_id, api_hash) as client:
            now = datetime.now(timezone.utc)
            all_links = set()
            time_ranges = [1, 3, 6, 12, 24]

            for hours in time_ranges:
                logging.info(f"📅 设置抓取时间范围: 最近 {hours} 小时")
                since = now - timedelta(hours=hours)
                group_stats.clear()
                protocol_stats.clear()

                results = await fetch_all_messages_with_rate_limit(client, group_links)
                any_valid_node = False

                for link, messages in results:
                    group_stats[link] = {"success": 0, "failed": 0}

                    for message in messages:
                        if message.date < since:
                            continue
                        found = url_pattern.findall(message.message or '')
                        all_links.update(found)

                        for idx, node in enumerate(found):
                            parsed = parse_node(node, idx)
                            if parsed:
                                group_stats[link]["success"] += 1
                                proto = parsed["type"]
                                protocol_stats[proto] = protocol_stats.get(proto, 0) + 1
                            else:
                                group_stats[link]["failed"] += 1

                if group_stats and any(stats["success"] > 0 for stats in group_stats.values()):
                    any_valid_node = True
                    break

            if not any_valid_node:
                logging.error("没有抓取到符合要求的节点，请检查群组配置或网络连接。")
                return

            unique_nodes = list(set(all_links))
            await generate_subscribe_file(unique_nodes)
            logging.info(f"💾 保存节点配置完成，节点数：{len(unique_nodes)}")

            logging.info("📊 群组抓取统计:")
            for group_link, stats in group_stats.items():
                logging.info(f"{group_link}: 成功 {stats['success']}，失败 {stats['failed']}")

            logging.info("📦 协议统计:")
            for proto, count in protocol_stats.items():
                logging.info(f"{proto}: {count}")

    except Exception as e:
        logging.error(f"🛑 执行失败: {e}")

    finally:
        if os.path.exists(session_file_path):
            os.remove(session_file_path)
            logging.info("🧹 已清理 session 文件")

if __name__ == "__main__":
    asyncio.run(main())
