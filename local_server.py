#!/usr/bin/env python3
"""
本地 WebSocket 服务器 — 替代云端 global.yunatt.com:7792
协议: WebSocket, 路径 /pub/chat
注册ACK: {"ret":"reg","result":true,"cloudtime":"YYYY-MM-DD HH:MM:SS"}
用法: python3 local_server.py
"""
import asyncio
import json
import logging
from datetime import datetime

try:
    import websockets
except ImportError:
    print("请先安装: pip install websockets")
    raise

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

swipe_events = []

async def handle_device(websocket):
    path = websocket.request.path if hasattr(websocket, "request") else "?"
    addr = websocket.remote_address
    log.info(f"设备连接: {addr}  path={path}")

    try:
        async for message in websocket:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 打印原始内容
            if isinstance(message, bytes):
                log.info(f"← binary {len(message)}B: {message[:48].hex()}")
                try:
                    message = message.decode("utf-8")
                except Exception:
                    log.info("  (无法解码为 UTF-8)")
                    continue

            log.info(f"← text: {message}")

            try:
                data = json.loads(message)
            except Exception:
                log.info("  (非 JSON，忽略)")
                continue

            # 设备用 "cmd" 字段，云端响应用 "ret" 字段
            cmd = data.get("cmd") or data.get("ret", "")
            await dispatch(websocket, cmd, data, now)

    except Exception as e:
        log.info(f"连接断开: {e}")
    finally:
        log.info(f"设备离线: {addr}")

async def dispatch(ws, cmd, data, now):
    if cmd == "reg":
        ack = {"ret": "reg", "result": True, "cloudtime": now}
        await ws.send(json.dumps(ack))
        log.info(f"→ 注册ACK")

    elif cmd == "heartbeat":
        ack = {"ret": "heartbeat", "result": True, "cloudtime": now}
        await ws.send(json.dumps(ack))
        log.info(f"→ 心跳ACK")

    elif cmd == "sendlog":
        # 刷脸/刷卡日志，必须回传 logindex
        logindex = data.get("logindex", 0)
        records = data.get("record", [])
        for r in records:
            log.info(f"★ 刷脸/刷卡: name={r.get('name')} mode={r.get('mode')} "
                     f"time={r.get('time')} enrollid={r.get('enrollid')}")
            swipe_events.append({"time": now, "record": r})
        ack = {"ret": "sendlog", "result": True, "logindex": logindex}
        await ws.send(json.dumps(ack))
        log.info(f"→ sendlog ACK logindex={logindex}")

    else:
        log.info(f"★★★ 未知事件 cmd={cmd!r}: {json.dumps(data, ensure_ascii=False)} ★★★")
        swipe_events.append({"time": now, "data": data})
        ack = {"ret": cmd, "result": True, "cloudtime": now}
        await ws.send(json.dumps(ack))

async def main():
    host, port = "0.0.0.0", 7792
    log.info(f"本地 WebSocket 服务器启动: ws://{host}:{port}/pub/chat")
    log.info("在设备上将服务器地址设为 Mac IP（10.20.20.61），端口 7792")
    log.info("等待设备连接...\n")

    async with websockets.serve(handle_device, host, port):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info(f"\n停止，共收到 {len(swipe_events)} 个事件")
        for e in swipe_events:
            print(e)
