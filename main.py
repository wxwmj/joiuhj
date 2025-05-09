import base64
import json
import os
import re
import time
import logging
from telethon.sync import TelegramClient
from telethon.tl.types import Message
from dotenv import load_dotenv

load_dotenv()

# 读取环境变量（已混淆命名）
API_ID = int(os.getenv("S_ID"))
API_HASH = os.getenv("S_HASH")
SESSION_B64 = os.getenv("S_SSN")
GROUPS = os.getenv("S_GPS").split(',')

# 解码 session
SESSION = base64.b64decode(SESSION_B64)

# 日志配置
logging.basicConfig(level=logging.INFO)

# 支持协议
SUPPORTED_PROTOCOLS = ["vmess", "ss", "trojan", "vless", "tuic", "hysteria", "hysteria2"]


def is_valid_node(text):
    return any(text.strip().startswith(proto + "://") for proto in SUPPORTED_PROTOCOLS)


def extract_nodes_from_text(text):
    urls = re.findall(r'(?:' + '|'.join(SUPPORTED_PROTOCOLS) + r')://[^\s]+', text)
    return [url.strip() for url in urls if is_valid_node(url)]


def parse_node(url, index):
    try:
        protocol = url.split("://")[0].lower()
        content = url[len(protocol) + 3:]

        if protocol == "vmess":
            try:
                raw_json = base64.b64decode(content).decode()
                conf = json.loads(raw_json)
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
                logging.debug(f"[vmess] 解析失败: {e}")
                return None

        elif protocol in ["trojan", "vless", "tuic", "hysteria", "hysteria2"]:
            try:
                userinfo, hostport = content.split("@")
                if ":" not in hostport:
                    logging.debug(f"[{protocol}] 地址格式错误: {hostport}")
                    return None
                host, port = hostport.split(":")
                node = {
                    "name": f"{protocol}_{index}",
                    "type": protocol,
                    "server": host,
                    "port": int(port),
                    "udp": True
                }
                if protocol == "trojan":
                    node["password"] = userinfo
                elif protocol == "vless":
                    node["uuid"] = userinfo
                    node["encryption"] = "none"
                else:
                    node["password"] = userinfo
                return node
            except Exception as e:
                logging.debug(f"[{protocol}] 解析失败: {e}")
                return None

        elif protocol == "ss":
            try:
                if "#" in content:
                    content = content.split("#")[0]
                if "@" in content:
                    method_pwd_b64, server_part = content.split("@")
                    method, password = base64.b64decode(method_pwd_b64 + "===").decode().split(":")
                else:
                    decoded = base64.b64decode(content + "===").decode()
                    method_pwd, server_part = decoded.split("@")
                    method, password = method_pwd.split(":")
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
                logging.debug(f"[ss] 解析失败: {e}")
                return None

        else:
            logging.debug(f"未知协议类型: {protocol}")
            return None

    except Exception as e:
        logging.debug(f"通用节点解析失败: {e}")
        return None


def generate_subscribe_file(nodes, filename="sub"):
    try:
        raw = "\n".join(nodes).encode()
        encoded = base64.b64encode(raw).decode()
        with open(filename, "w", encoding="utf-8") as f:
            f.write(encoded)
        logging.info(f"订阅文件生成成功，共 {len(nodes)} 条节点")
    except Exception as e:
        logging.error(f"生成订阅文件失败: {e}")


def main():
    messages = []
    try:
        with open("session.session", "wb") as f:
            f.write(SESSION)
        with TelegramClient("session", API_ID, API_HASH) as client:
            for group in GROUPS:
                try:
                    entity = client.get_entity(group)
                    for msg in client.iter_messages(entity, limit=1000):
                        if isinstance(msg, Message) and hasattr(msg, 'text') and msg.text:
                            if msg.date.timestamp() > time.time() - 86400:
                                messages.append((group, msg.text))
                except Exception as e:
                    logging.warning(f"获取 {group} 消息失败: {e}")
    finally:
        if os.path.exists("session.session"):
            os.remove("session.session")

    nodes = []
    dedup_set = set()
    group_stats = {}

    for link, text in messages:
        found_nodes = extract_nodes_from_text(text)
        if not found_nodes:
            continue
        if link not in group_stats:
            group_stats[link] = {"total": 0, "success": 0, "failed": 0}
        for idx, node in enumerate(found_nodes):
            group_stats[link]["total"] += 1
            parsed = parse_node(node, idx)
            if parsed:
                if node not in dedup_set:
                    dedup_set.add(node)
                    nodes.append(node)
                group_stats[link]["success"] += 1
            else:
                group_stats[link]["failed"] += 1

    generate_subscribe_file(nodes)

    logging.info("抓取统计：")
    for group, stats in group_stats.items():
        logging.info(f"{group} - 总数: {stats['total']} 成功: {stats['success']} 失败: {stats['failed']}")


if __name__ == "__main__":
    main()
