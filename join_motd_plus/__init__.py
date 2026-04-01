import json
import random
import threading
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Any, Callable, Dict, List, Optional, Union
from urllib import error, parse, request

from mcdreforged.api.all import *


class ServerInfo(Serializable):
    name: str
    display: Optional[str] = None
    description: Optional[str] = None
    category: str = ""

    @classmethod
    def from_object(cls, obj) -> "ServerInfo":
        if isinstance(obj, cls):
            return obj
        return ServerInfo(name=str(obj))


class Config(Serializable):
    main_server_name: str = "Survival Server"
    server_name: str = "Survival Server"
    commonJsonDataPath: Optional[str] = None
    server_list: List[Union[str, ServerInfo]] = [
        "survival",
        "lobby",
        ServerInfo(name="creative1", description="CMP Server#1", category="CMP"),
        ServerInfo(name="creative2", description="CMP Server#2", category="CMP"),
    ]
    start_day: Optional[str] = None
    daycount_plugin_ids: List[str] = [
        "mcd_daycount",
        "day_count_reforged",
        "daycount_nbt",
    ]
    auto_reload_interval: Optional[float] = None
    custom_text: str = "祝你今天也有好心情"
    hitokoto_api: str = "https://v1.hitokoto.cn/?encode=text"
    location_api: str = "https://api.ip.sb/geoip/{ip}"
    http_timeout: float = 2.5
    random_text_fallback: str = "欢迎回来，愿你有不错的一天"
    unknown_ip: str = "Unknown"
    unknown_location: str = "Unknown"
    unknown_hitokoto: str = "今天也要元气满满"
    pass_day_for_new_player: int = 0
    permission_motd: int = 0
    permission_reload: int = 3
    permission_server: int = 0


MOTD_PREFIX = "!!motd"
SERVER_PREFIX = "!!server"
ConfigFilePath = Path("config/joinMOTD/config.json")
RandomTextFilePath = Path("config/joinMOTD/random_text.txt")
LastJoinTimeFilePath = Path("config/joinMOTD/last_join_time.json")
TimeFormat = "%Y-%m-%d_%H:%M:%S"

config: Config
random_text_lines: List[str] = []
last_join_times: Dict[str, datetime] = {}
player_login_ips: Dict[str, str] = {}
DataLock = threading.RLock()
UnloadFlag = threading.Event()


def get_day(server: ServerInterface) -> str:
    try:
        if config.start_day is not None:
            start_day = datetime.strptime(config.start_day, "%Y-%m-%d")
            return str((datetime.now() - start_day).days)
    except Exception:
        pass

    for pid in config.daycount_plugin_ids:
        api = server.get_plugin_instance(pid)
        if hasattr(api, "getday") and callable(api.getday):
            return api.getday()
    try:
        import daycount

        return daycount.getday()
    except Exception:
        return "?"


def fetch_json(server: ServerInterface, url: str) -> Optional[dict]:
    text = fetch_text(server, url)
    if text is None:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except ValueError as exc:
        server.logger.warning("Parse json from %r failed: %s", url, exc)
        return None


def fetch_text(server: ServerInterface, url: str) -> Optional[str]:
    try:
        req = request.Request(url, headers={"User-Agent": "join_motd_plus/2.0"})
        with request.urlopen(req, timeout=max(0.1, config.http_timeout)) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except (error.URLError, TimeoutError, OSError) as exc:
        server.logger.warning("Request %r failed: %s", url, exc)
        return None


def get_hitokoto(server: ServerInterface) -> str:
    text = fetch_text(server, config.hitokoto_api)
    if text is None:
        return config.unknown_hitokoto
    text = text.strip()
    return text if text else config.unknown_hitokoto


def normalize_ip(ip: str) -> str:
    ip = ip.strip()
    if ip.count(":") == 1 and "." in ip:
        return ip.split(":", 1)[0]
    return ip


def get_location(server: ServerInterface, ip: str) -> str:
    ip = normalize_ip(ip)
    if not ip or ip == config.unknown_ip:
        return config.unknown_location

    quoted_ip = parse.quote(ip, safe="")
    try:
        url = config.location_api.format(ip=quoted_ip)
    except Exception:
        url = config.location_api + quoted_ip

    data = fetch_json(server, url)
    if not isinstance(data, dict):
        return config.unknown_location

    city = str(data.get("city", "")).strip()
    country = str(data.get("country", "")).strip()
    if city and country:
        return "{},{}".format(city, country)
    if city:
        return city
    if country:
        return country
    return config.unknown_location


def load_random_text(server: PluginServerInterface) -> None:
    RandomTextFilePath.parent.mkdir(parents=True, exist_ok=True)
    if not RandomTextFilePath.exists():
        RandomTextFilePath.write_text(config.random_text_fallback + "\n", encoding="utf8")

    lines = []
    try:
        for line in RandomTextFilePath.read_text(encoding="utf8").splitlines():
            line = line.strip()
            if len(line) > 0:
                lines.append(line)
    except Exception as exc:
        server.logger.error("Load random text from %r failed: %s", str(RandomTextFilePath), exc)

    global random_text_lines
    random_text_lines = lines


def get_random_text() -> str:
    if len(random_text_lines) > 0:
        return random.choice(random_text_lines)
    return config.random_text_fallback


def load_last_join_times(server: PluginServerInterface) -> None:
    LastJoinTimeFilePath.parent.mkdir(parents=True, exist_ok=True)
    if not LastJoinTimeFilePath.exists():
        LastJoinTimeFilePath.write_text("{}", encoding="utf8")

    loaded_data: Dict[str, datetime] = {}
    try:
        data = json.loads(LastJoinTimeFilePath.read_text(encoding="utf8"))
        if isinstance(data, dict):
            for player_name, time_str in data.items():
                if isinstance(player_name, str) and isinstance(time_str, str):
                    loaded_data[player_name] = datetime.strptime(time_str, TimeFormat)
    except Exception as exc:
        server.logger.error("Load last join data from %r failed: %s", str(LastJoinTimeFilePath), exc)

    with DataLock:
        last_join_times.clear()
        last_join_times.update(loaded_data)


def save_last_join_times(server: ServerInterface) -> None:
    try:
        with DataLock:
            data = {
                player_name: join_time.strftime(TimeFormat)
                for player_name, join_time in last_join_times.items()
            }
        LastJoinTimeFilePath.parent.mkdir(parents=True, exist_ok=True)
        LastJoinTimeFilePath.write_text(json.dumps(data, ensure_ascii=False), encoding="utf8")
    except Exception as exc:
        server.logger.error("Save last join data to %r failed: %s", str(LastJoinTimeFilePath), exc)


def save_player_last_join_time(server: ServerInterface, player_name: str, join_time: Optional[datetime] = None) -> None:
    with DataLock:
        last_join_times[player_name] = datetime.now() if join_time is None else join_time
    save_last_join_times(server)


def get_pass_day(player_name: str) -> int:
    with DataLock:
        last_time = last_join_times.get(player_name)
    if last_time is None:
        return config.pass_day_for_new_player
    return max(0, (datetime.now() - last_time).days)


def get_real_ip(player_name: str) -> str:
    with DataLock:
        ip = player_login_ips.get(player_name)
    return normalize_ip(ip) if isinstance(ip, str) and len(ip.strip()) > 0 else config.unknown_ip


def wait_for_real_ip(player_name: str, timeout: float = 1.0, interval: float = 0.1) -> str:
    remain = max(0.0, timeout)
    while remain > 0:
        ip = get_real_ip(player_name)
        if ip != config.unknown_ip:
            return ip
        sleep(interval)
        remain -= interval
    return get_real_ip(player_name)


def has_permission(src: CommandSource, level: int) -> bool:
    level = int(level)
    try:
        if src.has_permission(level):
            return True
    except Exception:
        pass

    try:
        return int(src.get_permission_level()) >= level
    except Exception:
        pass

    try:
        return int(getattr(src, "permission_level")) >= level
    except Exception:
        return False


def require_permission(src: CommandSource, level: int, command_name: str) -> bool:
    if has_permission(src, level):
        return True
    src.reply("§c权限不足：执行 {} 需要权限等级 {}§r".format(command_name, int(level)))
    return False


def build_server_list_messages() -> List[RTextBase]:
    server_entries: List[ServerInfo] = [ServerInfo.from_object(entry) for entry in config.server_list]
    messages: List[RTextBase] = []
    for info in server_entries:
        command = "/server {}".format(info.name)
        hover_text = command
        if info.description is not None:
            hover_text = "§e{}§r\n{}".format(info.description, command)
        display_text = info.display or info.name
        messages.append(RText("§3[{}]§r".format(display_text)).h(hover_text).c(RAction.run_command, command))
    return messages


def display_server_list(reply: Callable[[Union[str, RTextBase]], Any], *, with_title: bool = True) -> None:
    messages = build_server_list_messages()
    if with_title:
        reply("§b可用服务器列表§r")
    if len(messages) > 0:
        reply(RTextBase.join(" ", messages))
    else:
        reply("§7当前没有可用的服务器列表配置§r")


def display_motd(
    server: ServerInterface,
    reply: Callable[[Union[str, RTextBase]], Any],
    player_name: Optional[str] = None,
    real_ip: Optional[str] = None,
):
    player_name = player_name or "玩家"
    pass_day = get_pass_day(player_name)
    real_ip = real_ip or get_real_ip(player_name)
    location = get_location(server, real_ip)
    hitokoto = get_hitokoto(server)
    random_text = get_random_text()

    reply("§8§m-----------------------------------§r")
    reply("§b{}§r§7，欢迎回到 §6{}§r§7！§r".format(player_name, config.server_name))
    reply("§7这是 §6{}§r§7 开服的第 §e{}§r§7 天§r".format(config.main_server_name, get_day(server)))
    reply("")
    reply("§7您上次加入服务器距今已过 §a{}§r§7 天§r".format(pass_day))
    reply("§7您当前的IP属地：§b{}§r§7（§f{}§r§7）§r".format(location, real_ip))
    reply("")
    reply("§d[一言]§r §f{}§r".format(hitokoto))
    reply("§a[随机语录]§r §f{}§r".format(random_text))
    reply("§e[自定义文本]§r §f{}§r".format(config.custom_text))
    reply("")

    display_server_list(reply, with_title=False)
    reply("§8§m-----------------------------------§r")


@new_thread("JoinMOTDDisplay")
def display_join_motd(server: ServerInterface, player_name: str):
    real_ip = wait_for_real_ip(player_name)
    display_motd(server, lambda msg: server.tell(player_name, msg), player_name, real_ip)


def on_player_joined(server: ServerInterface, player_name, info):
    display_join_motd(server, player_name)


def on_player_left(server: ServerInterface, player_name):
    save_player_last_join_time(server, player_name)


def on_player_ip_login(server: PluginServerInterface, player_name: str, player_ip: str):
    with DataLock:
        player_login_ips[player_name] = player_ip


def reload_runtime_data(server: PluginServerInterface, echo_in_console: bool = True) -> None:
    load_config(server, echo_in_console=echo_in_console)
    load_last_join_times(server)


def on_motd_command(src: CommandSource):
    if not require_permission(src, config.permission_motd, MOTD_PREFIX):
        return
    display_motd(
        src.get_server(),
        src.reply,
        src.player if isinstance(src, PlayerCommandSource) else None,
    )


def on_motd_reload_command(server: PluginServerInterface, src: CommandSource):
    if not require_permission(src, config.permission_reload, "{} reload".format(MOTD_PREFIX)):
        return
    reload_runtime_data(server, echo_in_console=True)
    src.reply("§a[JoinMOTD] 配置和数据已重载§r")


def on_server_command(src: CommandSource):
    if not require_permission(src, config.permission_server, SERVER_PREFIX):
        return
    display_server_list(src.reply)


def on_load(server: PluginServerInterface, old):
    UnloadFlag.clear()
    reload_runtime_data(server, echo_in_console=True)

    server.register_help_message(MOTD_PREFIX, "显示欢迎消息，使用 !!motd reload 重载")
    server.register_help_message(SERVER_PREFIX, "显示可用服务器列表")
    server.register_command(
        Literal(MOTD_PREFIX)
        .runs(on_motd_command)
        .then(Literal("reload").runs(lambda src: on_motd_reload_command(server, src)))
    )
    server.register_command(Literal(SERVER_PREFIX).runs(on_server_command))
    server.register_event_listener("player_ip_logger.player_login", on_player_ip_login)

    def is_auto_reload_enabled() -> bool:
        return config.auto_reload_interval is not None and config.auto_reload_interval > 0

    def get_auto_reload_interval() -> float:
        return max(1.0, config.auto_reload_interval + random.random() * 0.2 - 0.1)

    if is_auto_reload_enabled():

        @new_thread("JoinMOTDAutoReload")
        def auto_reload():
            server.logger.debug("AutoReload thread start")
            while is_auto_reload_enabled() and UnloadFlag.wait(get_auto_reload_interval()) is False:
                server.logger.debug("Reloading config and random text")
                load_config(server, echo_in_console=False)
            server.logger.debug("AutoReload thread end")

        auto_reload()


def on_unload(server: PluginServerInterface):
    UnloadFlag.set()


def load_config(server: PluginServerInterface, echo_in_console: bool):
    ConfigFilePath.parent.mkdir(parents=True, exist_ok=True)
    new_config = server.load_config_simple(
        file_name=str(ConfigFilePath),
        in_data_folder=False,
        target_class=Config,
        echo_in_console=echo_in_console,
    )
    common_json_path = new_config.commonJsonDataPath
    if common_json_path is not None:
        server.logger.debug("Loading common config from %r", common_json_path)
        try:
            with open(common_json_path, "r", encoding="utf8") as file_handler:
                common_config_json = json.load(file_handler)

            new_config_json = new_config.serialize()
            new_config_json.update(common_config_json)
            new_config = Config.deserialize(new_config_json)
        except Exception as exc:
            server.logger.error("Load common config json from %r failed: %s", common_json_path, exc)

    global config
    config = new_config
    load_random_text(server)
