import asyncio
import os
import re
import logging
import yaml
import base64
import socket
import aiohttp
from dotenv import load_dotenv

load_dotenv()

from 设置.config import GROUP_LIST, PROXIES, HEADERS
from 配置.telegram_session import get_telegram_client
from 解析.node_parser import (
    parse_vmess_node, parse_ss_node, parse_trojan_node,
    parse_vless_node, parse_tuic_node,
    parse_hysteria_node, parse_hysteria2_node
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

VALID_PROTOCOLS = ('vmess://', 'ss://', 'trojan://', 'vless://', 'tuic://', 'hysteria://', 'hysteria2://')
MAX_DELAY_MS = 5000
THREAD_LIMIT = 32

# 测速函数（TCP Socket）
async def tcp_ping(host: str, port: int, timeout: float = 3) -> float:
    loop = asyncio.get_event_loop()
    start = loop.time()
    try:
        await asyncio.wait_for(loop.getaddrinfo(host, port), timeout)
        reader, writer = await asyncio.open_connection(host, port)
        writer.close()
        await writer.wait_closed()
        end = loop.time()
        return (end - start) * 1000
    except Exception:
        return float("inf")

# 提取链接
def extract_links(text):
    return [line.strip() for line in re.findall(r'((?:' + '|'.join(VALID_PROTOCOLS) + r')[^\s]+)', text)]

# 异步抓取
async def fetch_group_links(client, group):
    links = set()
    try:
        async for message in client.iter_messages(group, limit=100):
            if message.raw_text:
                for link in extract_links(message.raw_text):
                    links.add(link)
    except Exception as e:
        logging.warning(f"抓取 {group} 失败: {e}")
    return links

# 保存 base64 文件
async def generate_subscribe_file(links, filename="sub"):
    joined = "\n".join(links)
    encoded = base64.urlsafe_b64encode(joined.encode()).decode()
    with open(filename, "w", encoding="utf-8") as f:
        f.write(encoded)
    logging.info(f"📦 Base64 订阅文件生成完成: {filename}")

# 保存 YAML 文件
def convert_to_clash_config(parsed_nodes):
    proxies = []
    for node in parsed_nodes:
        if node["type"] == "vmess":
            clash_node = {
                "name": node["name"],
                "type": "vmess",
                "server": node["server"],
                "port": node["port"],
                "uuid": node["uuid"],
                "alterId": node.get("alterId", 0),
                "cipher": node.get("cipher", "auto"),
                "tls": node.get("tls", False),
            }
            proxies.append(clash_node)
        elif node["type"] in ["ss", "trojan", "vless", "tuic", "hysteria", "hysteria2"]:
            clash_node = node.copy()
            proxies.append(clash_node)

    clash_config = {
        "port": 7890,
        "socks-port": 7891,
        "allow-lan": True,
        "mode": "Rule",
        "log-level": "info",
        "proxies": proxies,
        "proxy-groups": [
            {
                "name": "Auto",
                "type": "url-test",
                "proxies": [p["name"] for p in proxies],
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300
            }
        ],
        "rules": ["MATCH,Auto"]
    }
    return clash_config

def save_yaml_config(nodes, filename="wxx.yaml"):
    try:
        config = convert_to_clash_config(nodes)
        with open(filename, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, sort_keys=False)
        logging.info(f"📄 YAML 配置文件已生成：{filename}")
    except Exception as e:
        logging.error(f"生成 YAML 配置失败: {e}")

# 主函数
async def main():
    client = await get_telegram_client()
    all_links = set()

    for group in GROUP_LIST:
        links = await fetch_group_links(client, group)
        all_links.update(links)
        logging.info(f"{group} 提取链接数: {len(links)}")

    logging.info(f"🎯 总共提取去重链接数: {len(all_links)}")

    # 并发测速
    semaphore = asyncio.Semaphore(THREAD_LIMIT)
    results = []

    async def test_node(link, index):
        for parser in [
            parse_vmess_node, parse_ss_node, parse_trojan_node,
            parse_vless_node, parse_tuic_node, parse_hysteria_node, parse_hysteria2_node
        ]:
            node = parser(link, index)
            if node:
                async with semaphore:
                    delay = await tcp_ping(node["server"], int(node["port"]))
                    if delay < MAX_DELAY_MS:
                        node["delay"] = round(delay)
                        return node
        return None

    tasks = [test_node(link, i) for i, link in enumerate(all_links)]
    results = await asyncio.gather(*tasks)
    good_nodes = [node for node in results if node]

    logging.info(f"✅ 可用节点数: {len(good_nodes)} / {len(all_links)}")

    # 输出
    await generate_subscribe_file([n["raw"] for n in good_nodes])
    save_yaml_config(good_nodes)

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
