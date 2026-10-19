# 1.1.0 本地验证记录

日期：2026-10-19。分支：`codex/multica-v1.1`；基线 `f74180e7`。本次为本地交付，不表示已推送 main 或发布 Release。

## 最终行为

- `/multica` 进入或恢复，exit/new/agent/stop/status/help 为子命令；agent 无参数只列选项。
- 普通模式支持“进入multica模式”“切换为multica工作”等口语；经过原有安全阶段和进入权限。退出仍需 `/multica exit`。
- 群聊仅转发开启者文字，其他成员保持普通 AstrBot 管线；回复在群内可见。旧群会话没有开启者信息时暂停；旧私聊可从唯一会话用户恢复开启者，均不在启动时回写磁盘。
- 统一放行名单：UID 放行用户的所有会话；私聊 UMO 仅匹配指定机器人私聊；群聊 UMO 放行该群成员使用指令。空名单拒绝所有人。
- 未获放行的 Multica 指令回复：`您没有使用Multica的权限，请联系管理员获取使用资格`。
- 普通自然语言创建 Issue 先生成草稿，120 秒内本人短码确认；权限、目标上下文、过期和重复确认均检查。
- stop 优先使本地旧队列失效；在途 POST 结算后再请求远端停止。不明确结果不自动重发。
- WebUI 移除旧群聊/私聊黑白名单控件，展示三种放行格式和范围；仅使用占位示例。智能体下拉支持名称/ID、搜索、自动选择和键盘操作。

## 验证

| 检查 | 结果 |
| --- | --- |
| Python 3.12.10 | 168 项测试通过 |
| Python 3.10.21 | 使用项目内隔离解释器，最终结果随最终验收复核 |
| Ruff check / format | 通过 |
| 两个 AstrBot 上游源码版本 | 集成用例执行，通过；没有跳过 |
| Edge / Playwright | 桌面 1440px、手机 390px/320px、浅色/暗色、中文/英文通过 |
| 浏览器错误 / 外部请求 / 手机横向溢出 | 0 / 0 / 0 |
| UID / 私聊 UMO / 群聊 UMO | 保存、刷新恢复与实际权限逻辑覆盖 |
| 工作区/项目选项、配置变更 | 归属验证、旧项目清理、配置保存竞态与持久化覆盖 |
| 智能体下拉 | 搜索、键盘选择、空结果、自动选择与手机弹层边界通过 |
| 旧配置 / 覆盖升级 | URL、Token、未知字段和备份保留 |

验证产物位于被 Git 忽略的 `.validation/`：`ui-results.json`、`screenshots/`、本地 HTTP/QQ Stub 及两个版本所需 AstrBot 源码。截图与浏览器样例均使用虚构标识或占位内容。

尚未启动真实 AstrBot 宿主、QQ 适配器和 Multica 服务，未调用真实 LLM。因此不报告模型准确率、真实远端停止效果、实际机器人平台发送成功或线上部署完成。需要在隔离账号/项目中进行最终联调；真实模型调用可能产生费用。

## 复现

```powershell
$env:REQUIRE_UPSTREAM_TESTS = '1'
python -m pytest
python -m ruff check .
python -m ruff format --check .
python scripts/build_package.py
```

浏览器服务与测试在不同终端运行；只监听本机，使用样例数据：

```powershell
python tests/browser/serve.py
```

```powershell
$env:PLAYWRIGHT_MODULE = (Resolve-Path '.validation/browser-tools/node_modules/playwright').Path
node tests/browser/agent-picker.cjs
node tests/browser/check.cjs
node tests/browser/races.cjs
```

测试使用现有 Edge，不需要 Docker。Python 3.10 解释器和测试工具只安装在项目 `.validation/` 下，未改变系统 Python 或 PATH。浏览器截图和完整检查前重启样例服务，以恢复初始会话。

## 升级与回滚

1. 备份原插件及 `plugin_data/astrbot_plugin_multica_bridge`，直接覆盖安装 ZIP，保留原数据目录。
2. 重载插件，在设置页检查 URL/Token，填写放行名单，读取工作区/项目和智能体并测试连接。
3. 旧群共享会话使用 `/multica new` 建立开启者会话，测试其他成员仍能正常使用 AstrBot。
4. 验证口语进入、Issue 草稿确认、stop、exit；在 QQ 和 Multica 两端核对结果。
5. 回滚时恢复原插件和备份数据，重载；不要卸载并删除数据。
