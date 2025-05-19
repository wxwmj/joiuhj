import os
import re
import base64
import asyncio
import logging
import yaml
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

# 配置区，环境变量读取
API_ID = int(os.getenv("API_ID", "123456"))
API_HASH = os.getenv("API_HASH", "your_api_hash_here")
SESSION_B64 = os.getenv("SESSION_B64", "")
GROUPS = os.getenv("GROUPS", "").split(",")  # 多群组用逗号分开
FETCH_HOURS = int(os.getenv("FETCH_HOURS", "24"))  # 抓取最近多少小时的消息

session_file = "session.session"


def load_session_from_b64(b64_str):
    data = base64.b64decode(b64_str)
    with open(session_file, "wb") as f:
        f.write(data)
    logging.info("Session 文件写入完成")


def parse_node_link(link, idx=0):
    # 这里只示范 vmess 和 ss 的简单解析，实际你可以扩展更多协议
    if link.startswith("vmess://"):
        try:
            raw = base64.b64decode(link[8:] + "==").decode("utf-8")
            import json
            obj = json.loads(raw)
            return {
                "type": "vmess",
                "name": obj.get("ps", f"vmess-{idx}"),
                "server": obj.get("add"),
                "port": int(obj.get("port", 0)),
                "uuid": obj.get("id"),
                "alterId": int(obj.get("aid", 0)),
                "cipher": obj.get("scy", "auto"),
                "tls": obj.get("tls") == "tls"
            }
        except Exception as e:
            logging.warning(f"vmess 解析失败: {e}")
            return None

    elif link.startswith("ss://"):
        # ss://加密方式:密码@地址:端口#备注  (简单示范)
        # 有些是ss://base64 加密信息形式，这里不做复杂解析
        return {
            "type": "ss",
            "name": f"ss-{idx}",
            "server": "example.com",
            "port": 443,
            "cipher": "aes-128-gcm",
            "password": "password"
        }

    # TODO: 这里补充 trojan, vless, tuic, hysteria 的解析函数

    return None


async def fetch_messages(client, group, since):
    all_links = []
    try:
        async for message in client.iter_messages(group, reverse=True):
            if message.date < since:
                break
            if message.message:
                # 简单提取所有可能的节点链接
                found_links = re.findall(r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+|tuic://[^\s]+|hysteria2?://[^\s]+)', message.message)
                all_links.extend(found_links)
    except Exception as e:
        logging.error(f"抓取消息失败: {e}")
    return all_links


def generate_clash_file(nodes):
    clash_config = {
        "port": 7890,
        "socks-port": 7891,
        "allow-lan": False,
        "mode": "Rule",
        "log-level": "info",
        "proxies": [],
        "proxy-groups": [
            {
                "name": "Auto",
                "type": "select",
                "proxies": []
            }
        ],
        "rules": ["MATCH,Auto"]
    }

    for node in nodes:
        proxy = None
        t = node.get("type")
        if t == "vmess":
            proxy = {
                "name": node["name"],
                "type": "vmess",
                "server": node["server"],
                "port": node["port"],
                "uuid": node["uuid"],
                "alterId": node.get("alterId", 0),
                "cipher": node.get("cipher", "auto"),
                "tls": node.get("tls", False),
            }
        elif t == "ss":
            proxy = {
                "name": node["name"],
                "type": "ss",
                "server": node["server"],
                "port": node["port"],
                "cipher": node["cipher"],
                "password": node["password"],
                "udp": True
            }
        # TODO: 补充 trojan, vless 节点配置转换
        if proxy:
            clash_config["proxies"].append(proxy)
            clash_config["proxy-groups"][0]["proxies"].append(node["name"])

    with open("clash", "w", encoding="utf-8") as f:
        yaml.dump(clash_config, f, allow_unicode=True)
    logging.info("🎉 Clash 配置文件已生成")


async def main():
    if SESSION_B64:
        load_session_from_b64(SESSION_B64)

    client = TelegramClient(session_file, API_ID, API_HASH)

    await client.start()
    logging.info("Telegram 客户端登录成功")

    since = datetime.now(timezone.utc) - timedelta(hours=FETCH_HOURS)

    all_links = []
    for group in GROUPS:
        logging.info(f"开始抓取群组 {group} 消息")
        links = await fetch_messages(client, group.strip(), since)
        all_links.extend(links)

    all_links = list(set(all_links))
    logging.info(f"共抓取到 {len(all_links)} 条节点链接")

    parsed_nodes = []
    for i, link in enumerate(all_links):
        node = parse_node_link(link, i)
        if node:
            parsed_nodes.append(node)

    # 生成 sub 文件（Base64订阅）
    sub_content = "\n".join(all_links).encode()
    with open("sub", "wb") as f:
        f.write(base64.b64encode(sub_content))
    logging.info("Base64 订阅文件 sub 已生成")

    # 生成 Clash 配置文件
    generate_clash_file(parsed_nodes)

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
