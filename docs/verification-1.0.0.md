# 1.0.0 验证记录

验证日期：2026-10-19。实现分支：`codex/multica-work-mode`。

## 结果

| 检查 | 本地结果 |
| --- | --- |
| Python 3.10.21 完整回归 | 114 passed |
| Python 3.12.10 完整回归 | 114 passed |
| Ruff | All checks passed |
| Edge / Playwright | 桌面 1440px、手机 390px / 320px 通过 |
| 手机横向溢出 | scrollWidth 与 viewportWidth 相等 |
| 页面运行错误、控制台错误、外部请求 | 均为 0 |

这里的测试使用本地 HTTP 服务、模拟 QQ 事件及上游 AstrBot 源码集成；未连接真实 QQ 账号、真实 Multica 服务，也未启动完整 AstrBot 宿主。上述结果不代表线上联调验收。CI 工作流配置相同 Python 矩阵，远程结果应查看对应提交的 Actions 记录，本表仅记录本地运行结果。

## 重点覆盖

- 旧版插件标识、数据目录、URL / Token 字段保持原样。加载时不回写配置；更新保存及重载后凭据保留。安装包解压覆盖旧插件的测试同样验证原配置字节不变。
- 首次写入保存原配置备份；空值、脱敏 Token 不会清除旧凭据；仅显式清除操作可清空 Token。损坏配置不会被默认值覆盖；保存保留未知字段。
- 群 A 成员共用该群的模式与 Chat，群 B、私聊 C、其他机器人实例分别隔离。进入、退出、重载、换 Chat、选择智能体、停止和消息去重均有覆盖。
- 已接管工作消息不会触发其他插件的命令过滤器、等待会话或默认模型。普通窗口及退出后的消息恢复原管线；原全局白名单、会话启停、限流和内容安全阶段仍执行。
- 禁止权限绕过、故障时回落普通模型、机器人消息回环；退出、卸载、换 Chat 后抑制迟到回复。卸载取消正在处理的本地操作。
- 所有回复分段都含 `【来自 Multica｜工作模式】`。目前仅支持文字；其他类型在工作模式内提示，不转交其他插件。
- Chat HTTP 测试通过真实本地 aiohttp 服务验证认证、URL 路径前缀、工作区头、分页、发送与停止接口。请求结果不明确时不会盲目重发。
- WebUI 使用真实插件配置 API，验证旧凭据保留、脱敏、热保存、刷新持久化、保存中继续编辑、连接测试、智能体列表、仅退出指定窗口、中英文和深浅主题。
- 浏览器竞态测试覆盖旧连接测试结果覆盖新配置，以及清除 Token 时覆盖后续输入的问题。测试数据为固定样例，不是真实工作会话。

## AstrBot 源码集成范围

分别读取以下版本未修改的消息调度器、命令组过滤器及白名单阶段，注入测试基础设施后执行路由测试：

- v4.27.2：`ad4fbfa90ca0c4ac2b30b3250e34dbf8fe7babbf`
- 4.29.1 源码快照：`e5e21b71aec5642f110eb115eb8e9a0d8028b7e5`

含负对照：普通高优先级消息监听器无法阻止其他插件的缺参数提示；新增入口兼容层可以在过滤器前接管。入口结构不兼容时不宣告成功进入工作模式。

## 复现

安装 `pytest pyyaml aiohttp ruff`，将上述源码放入 `.validation/AstrBot-4.27.2` 与 `.validation/AstrBot`。PowerShell：

```powershell
$env:REQUIRE_UPSTREAM_TESTS = '1'
python -m pytest -o addopts= --basetemp=.validation/test-run --tb=short -q
python -m ruff check .
python scripts/build_package.py
```

浏览器验证另外需要 Node.js、Playwright 和 Edge；不会成为插件运行依赖。先运行以下服务，然后在另一个终端运行浏览器测试。服务仅监听本机并使用 `.validation/ui-data` 下的样例配置：

```powershell
python tests/browser/serve.py
```

```powershell
# PLAYWRIGHT_MODULE 可选：指向本机 playwright 模块；默认 require('playwright')。
# BROWSER_EXECUTABLE 可选：指定浏览器可执行文件。
node tests/browser/check.cjs
node tests/browser/races.cjs
```

重复完整浏览器检查前应重新启动样例服务，以重置工作会话。截图与 JSON 报告生成于 `.validation/screenshots` 和 `.validation/ui-results.json`。

## 升级后人工验收

保留原插件数据直接更新。确认设置页原 URL / Token 仍在，测试连接并选择可用智能体。在群 A 输入 `/multica` 后连续追问，检查每条回复前缀、其他插件与模型无重复回复；同时检查群 B / 私聊 C 正常。输入 `/multica exit`，确认群 A 恢复普通模式。退出不取消远端任务，如需取消请先执行 `/multica stop`。

本次按用户要求以 1.0.0 推送至仓库 `dev` 分支；不创建 GitHub Release，不替换线上插件。远程 CI 结果以该提交的 Actions 运行记录为准。
