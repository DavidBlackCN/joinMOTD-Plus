joinMOTD-Plus
-------------

一个 MCDReforged 插件，基于[joinMOTD](https://github.com/TISUnion/joinMOTD)
玩家加入服务器时会收到欢迎 MOTD。

## 要求

- MCDR > 2.0
- [Player IP Logger](https://mcdreforged.com/zh-CN/plugin/player_ip_logger)

## 新增内容

- 玩家加入时间记录，显示上次加入服务器距今天数
- 玩家IP属地显示
- 一言，随机语录，自定义文本显示
- 更多命令和配置项

## 示例配置

- 配置文件：`config/joinMOTD/config.json`
- 随机语录：`config/joinMOTD/random_text.txt`
- 玩家上次加入记录：`config/joinMOTD/last_join_time.json`

## 配置说明

```json
	{
  "main_server_name": "Survival Server",	//服务器名称
  "server_name": "Survival Server",	//子服名称
  "start_day": null,	//开服日期
  "daycount_plugin_ids": [
    "mcd_daycount",
    "day_count_reforged",
    "daycount_nbt"
  ],
  "custom_text": "记得补充这里的自定义文案",	//自定义文本
  "hitokoto_api": "https://v1.hitokoto.cn/?encode=text",	//一言API
  "location_api": "https://api.ip.sb/geoip/{ip}",	//IP属地查询API
  "http_timeout": 2.5,	//超时
  "random_text_fallback": "欢迎回来，愿你有不错的一天",	//随机语录空值
  "unknown_ip": "Unknown",
  "unknown_location": "Unknown",
  "unknown_hitokoto": "今天也要元气满满",
  "pass_day_for_new_player": 0,	//新玩家显示据上次加入过0天
  "permission_motd": 0,		//!!motd权限
  "permission_reload": 3,	//!!reload权限
  "permission_server": 0,	//!!server权限
  "server_list": [
    "survival",
    "lobby",
    {
      "name": "creative1",
      "display": "创造服1",
      "description": "CMP Server#1",
      "category": "CMP"
    },
    {
      "name": "creative2",
      "display": "创造服2",
      "description": "CMP Server#2",
      "category": "CMP"
    }
  ]
}
```

如果配置文件中指定了 `start_day`（格式：`%Y-%m-%d`，如 `2026-04-01`），则将使用 `start_day` 计算开服时间，否则将尝试导入 daycount 插件进行开服时间获取

## 更新日志

- v1.0.0
    - Fork and rewrite

## 鸣谢

- [TISUnion/joinMOTD](https://github.com/TISUnion/joinMOTD) - 原插件
- [alex3236/joinMOTD_Plus](https://github.com/alex3236/joinMOTD_Plus) - 部分思路借鉴
- [mc-cloud-town/joinMOTD](https://github.com/mc-cloud-town/joinMOTD) - 部分思路借鉴
- [PFingan-Code/PF-player_ip_logger](https://github.com/PFingan-Code/PF-player_ip_logger) - 提供IP查询API
- [IP属地查询API](https://api.ip.sb/geoip/) - 提供IP属地查询API
- GPT-5.3-CodeX
