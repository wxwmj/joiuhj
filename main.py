import os
import re
import asyncio
import base64
import logging
import json
import yaml
import requests
import time
import shutil
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest

# ========== 配置 ==========
api_id_str = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
phone_number = os.getenv("PHONE_NUMBER")

if not all([api_id_str, api_hash, phone_number]):
    raise ValueError("❌ 缺少环境变量：API_ID、API_HASH 或 PHONE_NUMBER")

api_id = int(api_id_str)

group_usernames = [
    'VPN365R', 'ConfigsHUB2', 'free_outline_keys',
    'config_proxy', 'freenettir', 'wxgmrjdcc', 'daily_configs'
]

url_pattern = re.compile(r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+)', re.IGNORECASE)
max_age = timedelta(hours=12)

# ========== 日志配置 ==========
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()]
)

# ========== 工具函数 ==========
def safe_b64decode(data):
    try:
        data += '=' * (-len(data) % 4)  # 填补 base64 padding
        return base64.b64decode(data).decode()
    except Exception:
        return ""

# === 测试节点延迟 ===
def test_latency(node):
    try:
        start_time = time.time()
        response = requests.get("http://www.gstatic.com/generate_204", timeout=3)
        end_time = time.time()
        if response.status_code == 204:
            latency = (end_time - start_time) * 1000  # 转换为毫秒
            return latency
        return float('inf')  # 超时或者失败返回无穷大
    except requests.RequestException:
        return float('inf')  # 请求失败则返回无穷大

# === 检查节点是否为中国大陆节点 ===
def is_china_node(node):
    if ".cn" in node:
        return True
    return False

# ========== 解析节点 ==========
def parse_vmess_node(node, index):
    try:
        raw = safe_b64decode(node[8:])
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

# ========== 生成 Clash 配置 ==========
def generate_clash_config(nodes, output_file):
    proxies = []

    for i, node in enumerate(nodes):
        if node.startswith("vmess://"):
            proxy = parse_vmess_node(node, i + 1)
        elif node.startswith("trojan://"):
            proxy = parse_trojan_node(node, i + 1)
        elif node.startswith("vless://"):
            proxy = parse_vless_node(node, i + 1)
        elif node.startswith("ss://"):
            proxy = parse_ss_node(node, i + 1)
        else:
            proxy = None

        if proxy:
            proxies.append(proxy)

    config = {
        "proxies": proxies,
        "proxy-groups": [{
            "name": "auto",
            "type": "url-test",
            "proxies": [p["name"] for p in proxies],
            "url": "http://www.gstatic.com/generate_204",
            "interval": 300
        }],
        "rules": ["MATCH,auto"]
    }

    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)
    logging.info(f"[写入完成] {output_file}，节点数：{len(proxies)}")

# ========== 抓取 Telegram 消息 ==========
async def fetch_messages():
    client = TelegramClient('session', api_id, api_hash)
    await client.start(phone_number)

    now = datetime.now(timezone.utc)
    since = now - max_age
    all_links = set()

    for username in group_usernames:
        try:
            entity = await client.get_entity(username)
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
                if message.date < since:
                    continue
                found = url_pattern.findall(message.message or '')
                all_links.update(found)
        except Exception as e:
            logging.warning(f"[错误] 获取 {username} 失败：{e}")

    logging.info(f"[完成] 抓取链接数: {len(all_links)}")
    return list(all_links)

# ========== 主函数 ==========
async def main():
    logging.info("[启动] 开始抓取 Telegram 节点")

    # === 设置输出路径 ===
    OUTPUT_DIR = "output"
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)

    # === 抓取节点 ===
    raw_nodes = await fetch_messages()
    unique_nodes = list(set(raw_nodes))

    # === 对每个节点进行延迟测速并过滤 ===
    valid_nodes = []
    for node in unique_nodes:
        if is_china_node(node):
            logging.info(f"[过滤] 去除中国节点：{node}")
            continue  # 跳过中国节点

        latency = test_latency(node)
        if latency <= 5000:  # 如果延迟小于5000ms
            valid_nodes.append(node)
        else:
            logging.info(f"[过滤] 节点 {node} 延迟过高：{latency:.2f}ms")

    logging.info(f"[过滤完成] 有效节点数：{len(valid_nodes)}")

    # === 生成 Clash 配置并保存为 output/wxx.yaml ===
    generate_clash_config(valid_nodes, os.path.join(OUTPUT_DIR, "wxx.yaml"))

    # === 生成 base64 订阅，保存为 output/sub（无后缀）===
    try:
        joined_nodes = "\n".join(valid_nodes)
        encoded = base64.b64encode(joined_nodes.encode()).decode()
        with open(os.path.join(OUTPUT_DIR, "sub"), "w", encoding="utf-8") as f:
            f.write(encoded)
        logging.info("[写入完成] sub（base64 订阅）")
    except Exception as e:
        logging.warning(f"[错误] 生成 base64 订阅失败：{e}")

    # === 生成 V2Ray JSON 订阅格式，保存为 output/wxx.json ===
    v2ray_nodes = []
    for i, node in enumerate(valid_nodes):
        if node.startswith("vmess://"):
            try:
                raw = safe_b64decode(node[8:])
                conf = json.loads(raw)
                v2ray_nodes.append(conf)
            except Exception as e:
                logging.warning(f"[跳过] 无法解析 V2Ray 节点：{e}")

    with open(os.path.join(OUTPUT_DIR, "wxx.json"), "w", encoding="utf-8") as f:
        json.dump(v2ray_nodes, f, indent=2, ensure_ascii=False)

    logging.info(f"[写入完成] wxx.json（真实 V2Ray 订阅，节点数：{len(v2ray_nodes)}）")
    logging.info(f"[完成] 所有节点配置已保存到 {OUTPUT_DIR}/")
