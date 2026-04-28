DOMAIN = "yunatt"
CONF_PORT = "port"
SIGNAL_ACCESS_EVENT = f"{DOMAIN}_access_event"
SIGNAL_DOOR_OPEN    = f"{DOMAIN}_door_open"
SIGNAL_ONLINE       = f"{DOMAIN}_online"

OFFLINE_TIMEOUT = 180  # 秒，无连接后判定离线
DOOR_OPEN_SECONDS = 3  # 门打开传感器亮灯时长
