"""Multica 桥接插件主入口。

将 AstrBot 接入 Multica 平台：连接测试、成本报表同步、诊断结果推送。
所有配置通过 WebUI 设置页管理，修改后自动保存热生效。
"""

from __future__ import annotations

from astrbot import logger
from astrbot.api.star import Context, Star

from .web_api import WebApiMixin


class Main(WebApiMixin, Star):
    """Multica 桥接插件入口。

    继承 WebApiMixin 注册 REST API（/config、/actions/save_config、
    /actions/test_connection、/actions/sync），Star 提供 AstrBot 运行时能力。
    """

    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        self.context = context
        self.config = config or {}

    async def initialize(self) -> None:
        """插件加载时初始化：构建运行时配置 + 注册 Web API。"""
        try:
            from .config import CONFIG_DEFAULTS, deep_merge, load_plugin_config

            data_dir = str(self.get_data_dir())
            self._data_dir = data_dir
            self.cfg = deep_merge(
                CONFIG_DEFAULTS,
                load_plugin_config(data_dir),
            )
        except Exception as e:
            logger.warning("[multica_bridge] 加载配置失败，使用默认值: %s", e)
            from .config import CONFIG_DEFAULTS

            self.cfg = dict(CONFIG_DEFAULTS)

        try:
            self.register_routes()
        except Exception as e:
            logger.warning("[multica_bridge] Web API 注册失败: %s", e)
