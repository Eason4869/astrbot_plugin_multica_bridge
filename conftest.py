"""测试夹具：把插件目录注册为一个包，使模块间的相对导入可用。

插件在生产环境中由 AstrBot 以 ``data.plugins.<插件目录名>`` 导入，
因此源码使用相对导入；单元测试里用一个固定包名指向仓库根目录即可。
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGE = "astrbot_plugin_multica_bridge"

if PACKAGE not in sys.modules:
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT)]  # type: ignore[attr-defined]
    sys.modules[PACKAGE] = package
