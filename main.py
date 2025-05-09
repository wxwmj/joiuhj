import os
import base64
import logging
import json
import yaml
import re
import asyncio
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest

# ========= 混淆环境变量 =========
_k1 = os.getenv("_k1")  # API_ID
_k2 = os.getenv("_k2")  # API_HASH
_k3 = os.getenv("_k3")  # SESSION_B64

if not all([_k1, _k2, _k3]):
    raise RuntimeError("❌ 缺少必要环境变量：_k1、_k2 或 _k3")

_k1 = int(_k1)

# ========= 写入 Session 文件 =========
_xfile = "x.dat"
with open(_xfile, "wb") as _fx:
    _fx.write(base64.b64decode(_k3))

# ========= 日志设置 =========
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()]
)

# ========= Telegram 群组 =========
_groups = [
    'VPN365R', 'ConfigsHUB2', 'free_outline_keys',
    'config_proxy', 'freenettir', 'wxgmrjdcc', 'daily_configs'
]

# ========= 匹配链接 =========
_pattern = re.compile(r'(vmess://[^\s]+|ss://[^\s]+|trojan://[^\s]+|vless://[^\s]+)', re.IGNORECASE)

_max_age = timedelta(hours=12)

# ========= 解析函数 =========
def _vmess(n, i):
    try:
        _raw = base64.b64decode(n[8:])
        if not _raw:
            return None
        _c = json.loads(_raw)
        return {
            "name": f"vmess_{i}",
            "type": "vmess",
            "server": _c["add"],
            "port": int(_c["port"]),
            "uuid": _c["id"],
            "alterId": int(_c.get("aid", 0)),
            "cipher": "auto",
            "tls": _c.get("tls", "none") == "tls",
        }
    except Exception as e:
        logging.warning(f"[解析失败] vmess：{e}")
        return None

def _trojan(u, i):
    try:
        _r = u[9:].split("@")
        _p = _r[0]
        _hp = _r[1].split("?")[0].split(":")
        if len(_hp) < 2:
            return None
        return {
            "name": f"trojan_{i}",
            "type": "trojan",
            "server": _hp[0],
            "port": int(_hp[1]),
            "password": _p,
            "udp": True
        }
    except Exception as e:
        logging.warning(f"[解析失败] trojan：{e}")
        return None

def _vless(u, i):
    try:
        _r = u[8:].split("@")
        _id = _r[0]
        _hp = _r[1].split("?")[0].split(":")
        if len(_hp) < 2:
            return None
        return {
            "name": f"vless_{i}",
            "type": "vless",
            "server": _hp[0],
            "port": int(_hp[1]),
            "uuid": _id,
            "encryption": "none",
            "udp": True
        }
    except Exception as e:
        logging.warning(f"[解析失败] vless：{e}")
        return None

def _ss(u, i):
    try:
        _r = u[5:].split("#")[0]
        if "@" in _r:
            _mp, _sp = _r.split("@")
            _m, _pw = base64.b64decode(_mp + '===').decode().split(":")
        else:
            _d = base64.b64decode(_r + '===').decode()
            _mp, _sp = _d.split("@")
            _m, _pw = _mp.split(":")
        _srv, _pt = _sp.split(":")
        return {
            "name": f"ss_{i}",
            "type": "ss",
            "server": _srv,
            "port": int(_pt),
            "cipher": _m,
            "password": _pw,
            "udp": True
        }
    except Exception as e:
        logging.warning(f"[解析失败] ss：{e}")
        return None

# ========= 生成配置 =========
def _gen_cfg(_nodes):
    _out = []
    for i, _n in enumerate(_nodes):
        if _n.startswith("vmess://"):
            _p = _vmess(_n, i + 1)
        elif _n.startswith("trojan://"):
            _p = _trojan(_n, i + 1)
        elif _n.startswith("vless://"):
            _p = _vless(_n, i + 1)
        elif _n.startswith("ss://"):
            _p = _ss(_n, i + 1)
        else:
            _p = None
        if _p:
            _out.append(_p)

    _cfg = {
        "proxies": _out,
        "proxy-groups": [{
            "name": "auto",
            "type": "url-test",
            "proxies": [p["name"] for p in _out],
            "url": "http://www.gstatic.com/generate_204",
            "interval": 300
        }],
        "rules": ["MATCH,auto"]
    }
    with open("wxx.yaml", "w", encoding="utf-8") as _f:
        yaml.dump(_cfg, _f, allow_unicode=True)
    logging.info(f"[写入完成] wxx.yaml，节点数：{len(_out)}")

# ========= 抓取消息 =========
async def _fetch():
    _c = TelegramClient(_xfile, _k1, _k2)
    try:
        await _c.start()
        _now = datetime.now(timezone.utc)
        _since = _now - _max_age
        _links = set()

        for g in _groups:
            try:
                _e = await _c.get_entity(g)
                _h = await _c(GetHistoryRequest(peer=_e, limit=100, offset_date=None,
                                                offset_id=0, max_id=0, min_id=0,
                                                add_offset=0, hash=0))
                for m in _h.messages:
                    if m.date < _since:
                        continue
                    _found = _pattern.findall(m.message or '')
                    _links.update(_found)
            except Exception as e:
                logging.warning(f"[错误] 获取 {g} 失败：{e}")

        logging.info(f"[完成] 抓取链接数: {len(_links)}")
        return list(_links)
    except Exception as e:
        logging.error(f"登录失败: {e}")
        return []

# ========= 主入口 =========
async def main():
    logging.info("[启动] 开始抓取 Telegram 节点")
    _r = await _fetch()
    _u = list(set(_r))

    with open("sub", "w", encoding="utf-8") as f:
        for n in _u:
            f.write(n + "\n")

    _gen_cfg(_u)

    try:
        _b64 = base64.b64encode("\n".join(_u).encode()).decode()
        with open("wxx.json", "w", encoding="utf-8") as f:
            f.write(_b64)
        logging.info("[写入完成] wxx.json")
    except Exception as e:
        logging.warning(f"[错误] base64 生成失败：{e}")

    logging.info(f"[完成] 节点数：{len(_u)}")

if __name__ == "__main__":
    asyncio.run(main())
