# Yunatt 门禁 — Home Assistant 本地集成

将 **Yunatt / 天宇智控** 系列人脸识别门禁终端（型号 TM-AI07F / AiFace）接入 Home Assistant，完全**本地运行**，无需依赖云端平台。

## 功能

- 实时接收刷脸、刷指纹、刷卡事件（延迟 < 2 秒）
- 在 HA 中触发自动化（开灯、发通知、记录日志等）
- 传感器显示最近一次进出记录（姓名、方式、时间）
- 支持多用户识别（按 enrollid / name 区分）

## 工作原理

设备通过 **WebSocket**（端口 7792，路径 `/pub/chat`）连接服务端并推送 JSON 事件。本集成在 HA 内启动一个轻量 WebSocket 服务器替代云端，设备配置指向本机 IP 即可完全离线运行。

```
门禁设备 ──WebSocket:7792──► Home Assistant (本集成)
                              └─ yunatt_access 事件
                              └─ sensor.yunatt_last_access
```

## 设备配置

在门禁设备管理界面（或 App）中将**服务器地址**修改为运行 HA 的机器 IP，**端口**改为 `7792`。

> 默认云端地址为 `global.yunatt.com:7792`，替换为本机 IP 后设备即连接本地服务。

## 安装

### 方式一：手动安装

1. 下载本仓库
2. 将 `custom_components/yunatt/` 复制到 HA 的 `custom_components/` 目录
3. 重启 Home Assistant

### 方式二：HACS（自定义仓库）

1. HACS → 右上角菜单 → 自定义仓库
2. 填入 `https://github.com/rudyll/yunatt-ha`，类型选 **Integration**
3. 搜索安装 "Yunatt 门禁"，重启 HA

## 添加集成

设置 → 集成 → 添加集成 → 搜索 **Yunatt** → 输入端口（默认 7792）→ 提交

## 实体

| 实体 | 说明 |
|------|------|
| `sensor.yunatt_last_access` | 最近一次进出的用户名，附带模式/时间属性 |

### 属性

| 属性 | 说明 |
|------|------|
| `mode` | 识别方式：`face` / `fingerprint` / `card` / `password` |
| `enrollid` | 设备内用户编号 |
| `time` | 事件发生时间 |
| `inout` | 进出方向（0=进，1=出） |
| `sn` | 设备序列号 |

## 自动化示例

```yaml
# 刷脸后发通知
automation:
  alias: "门禁刷脸通知"
  trigger:
    - platform: event
      event_type: yunatt_access
      event_data:
        mode_name: face
  action:
    - service: notify.mobile_app
      data:
        message: "{{ trigger.event.data.name }} 刷脸进入 ({{ trigger.event.data.time }})"
```

```yaml
# 特定用户触发场景
automation:
  alias: "回家模式"
  trigger:
    - platform: event
      event_type: yunatt_access
      event_data:
        name: "张三"
  action:
    - service: scene.turn_on
      target:
        entity_id: scene.home_welcome
```

## 事件数据格式

每次刷脸/刷卡触发 `yunatt_access` 事件，数据结构：

```json
{
  "sn": "AIPJXXXXXXXX",
  "name": "张三",
  "enrollid": 1,
  "mode": 8,
  "mode_name": "face",
  "inout": 0,
  "event": 0,
  "time": "2026-04-27 00:55:26",
  "aliasid": ""
}
```

| `mode` 值 | 含义 |
|-----------|------|
| 1 | 指纹 |
| 4 | 刷卡 |
| 8 | 人脸 |
| 128 | 密码 |

## 独立测试服务器

无需 HA 也可单独运行测试：

```bash
pip install websockets
python3 local_server.py
```

## 兼容设备

已在以下设备验证：

| 型号 | 固件 | 状态 |
|------|------|------|
| TM-AI07F (AiFace) | AiFP50V_v4.25 | ✅ 已验证 |

其他使用 `global.yunatt.com:7792` 云端的天宇门禁设备理论上兼容，欢迎反馈。

## 许可证

[MIT License](LICENSE)
