import asyncio
import base64
import logging
import re
from datetime import datetime, timedelta, timezone

import yaml
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import GetHistoryRequest

# =================== 配置区 ===================
api_id = 123456  # 你的api_id
api_hash = "your_api_hash"  # 你的api_hash
session_file_path = "session.session"  # Telegram登录session文件路径
group_links = [
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

]  # 需要抓取的Telegram群组链接

# 节点链接提取正则（支持 vmess、ss、trojan、vless、tuic、hysteria、hysteria2 等）
url_pattern = re.compile(r"(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+|tuic://[^\s]+|hysteria://[^\s]+|hysteria2://[^\s]+)")

# =================== 日志配置 ===================
logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

# =================== 节点解析示例 ===================
# 这里只写了 vmess 和 trojan 的示例解析，实际你需要补全所有协议的解析
def parse_vmess_node(node_str, idx):
    # 去掉 vmess:// 前缀
    if not node_str.startswith("vmess://"):
        return None
    try:
        data = base64.b64decode(node_str[8:]).decode()
        import json

        obj = json.loads(data)
        node_info = {
            "name": obj.get("ps", f"vmess_{idx}"),
            "type": "vmess",
            "server": obj.get("add"),
            "port": int(obj.get("port")),
            "uuid": obj.get("id"),
            "alterId": int(obj.get("aid", 0)),
            "cipher": obj.get("scy", "auto"),
            "tls": obj.get("tls", "") == "tls",
        }
        return node_info
    except Exception as e:
        logging.debug(f"vmess 解析失败: {e}")
        return None


def parse_trojan_node(node_str, idx):
    # trojan://password@server:port#name
    if not node_str.startswith("trojan://"):
        return None
    try:
        import urllib.parse

        url = node_str[9:]
        # 拆分参数
        parts = url.split("#")
        main = parts[0]
        name = urllib.parse.unquote(parts[1]) if len(parts) > 1 else f"trojan_{idx}"

        password, server_port = main.split("@")
        server, port = server_port.split(":")

        node_info = {
            "name": name,
            "type": "trojan",
            "server": server,
            "port": int(port),
            "password": password,
            "udp": True,
        }
        return node_info
    except Exception as e:
        logging.debug(f"trojan 解析失败: {e}")
        return None


# 你可以按照上面格式自行实现 parse_ss_node, parse_vless_node, parse_tuic_node, parse_hysteria_node, parse_hysteria2_node

# 这里为了示例只调用上述两个解析器
def parse_node(node_str, idx):
    parsers = [parse_vmess_node, parse_trojan_node]  # 你可以加入更多解析函数
    for parser in parsers:
        node = parser(node_str, idx)
        if node:
            return node
    return None


# =================== Telegram消息抓取 ===================
async def fetch_messages(client, group_link, limit=100):
    try:
        entity = await client.get_entity(group_link)
        messages = []
        offset_id = 0
        while True:
            history = await client(GetHistoryRequest(
                peer=entity,
                offset_id=offset_id,
                offset_date=None,
                add_offset=0,
                limit=limit,
                max_id=0,
                min_id=0,
                hash=0,
            ))
            if not history.messages:
                break
            messages.extend(history.messages)
            offset_id = history.messages[-1].id
            if len(messages) >= limit:
                break
        return messages
    except FloodWaitError as e:
        logging.warning(f"触发限速，等待 {e.seconds} 秒")
        await asyncio.sleep(e.seconds)
        return await fetch_messages(client, group_link, limit)
    except Exception as e:
        logging.error(f"抓取群组 {group_link} 失败: {e}")
        return []


# =================== 抓取所有群组 ===================
async def fetch_all_messages(client, group_links):
    tasks = []
    for group_link in group_links:
        tasks.append(fetch_messages(client, group_link))
    results = await asyncio.gather(*tasks)
    return list(zip(group_links, results))


# =================== 生成 base64 订阅文件 ===================
async def generate_subscribe_file(nodes):
    try:
        joined_nodes = "\n".join(nodes)
        encoded = base64.b64encode(joined_nodes.encode()).decode()
        with open("sub", "w", encoding="utf-8") as f:
            f.write(encoded)
        logging.info("🎉 订阅文件 sub 生成完毕")
    except Exception as e:
        logging.error(f"生成订阅文件失败: {e}")


# =================== 生成 wxx.yaml ===================
def generate_wxx_yaml(nodes_details):
    try:
        with open("wxx.yaml", "w", encoding="utf-8") as yaml_file:
            yaml.dump(nodes_details, yaml_file, default_flow_style=False, allow_unicode=True)
        logging.info("🎉 wxx.yaml 文件生成完毕")
    except Exception as e:
        logging.error(f"生成 wxx.yaml 文件失败: {e}")


# =================== 主流程 ===================
async def main():
    logging.info("🚀 开始抓取 Telegram 节点")

    client = TelegramClient(session_file_path, api_id, api_hash)

    try:
        await client.start()
        now = datetime.now(timezone.utc)

        all_links = set()
        nodes_details = []

        # 抓取最近24小时消息
        messages_data = await fetch_all_messages(client, group_links)

        for group_link, messages in messages_data:
            for message in messages:
                # 只抓取最近24小时的消息
                if (now - message.date).total_seconds() > 24 * 3600:
                    continue
                found_links = url_pattern.findall(message.message or "")
                for idx, link in enumerate(found_links):
                    all_links.add(link)
                    node_detail = parse_node(link, idx)
                    if node_detail:
                        nodes_details.append(node_detail)

        if not all_links:
            logging.error("⚠️ 没有抓取到任何节点链接")
            return

        unique_links = list(all_links)

        await generate_subscribe_file(unique_links)

        generate_wxx_yaml(nodes_details)

        logging.info(f"🎯 总共抓取节点数量：{len(unique_links)}")

    except Exception as e:
        logging.error(f"程序运行异常: {e}")

    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
