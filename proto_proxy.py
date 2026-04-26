#!/usr/bin/env python3
"""
透明 TCP 代理 — 转发设备流量到真实 yunatt.com 服务器，同时双向记录原始字节。
用法：python3 proto_proxy.py [--port 7005] [--remote-host www.yunatt.com] [--remote-port 7005]
"""

import asyncio
import datetime
import argparse

MAGIC = b'\xa5\x5a'
CMD_NAMES = {
    0x01: "设备注册",
    0x81: "注册ACK",
    0x02: "心跳",
    0x82: "心跳ACK",
    0x03: "刷卡/刷脸事件",
    0x83: "刷卡ACK",
    0x04: "开门指令",
    0x84: "开门ACK",
}


def hexdump(data: bytes, prefix: str = "  ") -> str:
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        asc_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{prefix}{i:04x}  {hex_part:<47}  {asc_part}")
    return "\n".join(lines)


def log_packet(direction: str, data: bytes):
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:12]
    arrow = "→ 设备→云" if direction == "up" else "← 云→设备"
    print(f"\n[{ts}] {arrow}  {len(data)} 字节:")
    print(hexdump(data))

    if len(data) >= 3 and data[:2] == MAGIC:
        cmd = data[2]
        name = CMD_NAMES.get(cmd, f"未知(0x{cmd:02x})")
        print(f"  *** 命令: {name} ***")

        if cmd == 0x03:
            print(f"  !!! 刷卡/刷脸事件 !!!")
            payload = data[4:]
            ascii_fields = [s.decode() for s in payload.split(b'\x00') if s and all(32 <= b < 127 for b in s)]
            if ascii_fields:
                print(f"      ASCII字段: {ascii_fields}")

    # 提取可读文本
    try:
        printable = "".join(chr(b) if 32 <= b < 127 else "" for b in data)
        if len(printable) > 4:
            print(f"  可读: {repr(printable[:200])}")
    except Exception:
        pass


async def handle_client(device_reader: asyncio.StreamReader, device_writer: asyncio.StreamWriter,
                        remote_host: str, remote_port: int):
    addr = device_writer.get_extra_info("peername")
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"\n[{ts}] ← 设备连接: {addr[0]}:{addr[1]}")

    try:
        cloud_reader, cloud_writer = await asyncio.wait_for(
            asyncio.open_connection(remote_host, remote_port), timeout=10
        )
        print(f"  → 已连接到 {remote_host}:{remote_port}")
    except Exception as e:
        print(f"  ✗ 无法连接云端: {e}")
        device_writer.close()
        return

    try:
        # 收设备数据，转发给云端
        while True:
            try:
                data = await asyncio.wait_for(device_reader.read(4096), timeout=5)
            except asyncio.TimeoutError:
                break
            if not data:
                break
            log_packet("up", data)
            cloud_writer.write(data)
            await cloud_writer.drain()

            # 等云端回应（最多 5 秒，可能有多个包）
            deadline = asyncio.get_event_loop().time() + 5
            while asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()
                try:
                    resp = await asyncio.wait_for(cloud_reader.read(4096), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                if not resp:
                    break
                log_packet("down", resp)
                device_writer.write(resp)
                await device_writer.drain()
                deadline = asyncio.get_event_loop().time() + 2  # 收到包后再等 2s

    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        for w in (cloud_writer, device_writer):
            try:
                w.close()
            except Exception:
                pass
    print(f"  连接结束 ({addr[0]})")


async def main(local_port: int, remote_host: str, remote_port: int):
    handler = lambda r, w: handle_client(r, w, remote_host, remote_port)
    server = await asyncio.start_server(handler, "0.0.0.0", local_port)
    print(f"透明代理启动: 本机:{local_port} ←→ {remote_host}:{remote_port}")
    print("所有设备流量将被记录并转发到云端\n")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7005)
    parser.add_argument("--remote-host", default="www.yunatt.com")
    parser.add_argument("--remote-port", type=int, default=7005)
    args = parser.parse_args()
    try:
        asyncio.run(main(args.port, args.remote_host, args.remote_port))
    except KeyboardInterrupt:
        print("\n停止")
