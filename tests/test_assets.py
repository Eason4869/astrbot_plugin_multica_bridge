"""仓库资产一致性测试：WebUI 页面、i18n、metadata 与 CHANGELOG。"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "settings" / "index.html"
I18N_DIR = ROOT / ".astrbot-plugin" / "i18n"
METADATA = ROOT / "metadata.yaml"
CHANGELOG = ROOT / "CHANGELOG.md"

# 前端 JS 依赖的元素 ID，改名会直接让设置页失效
REQUIRED_IDS = [
    "field-enabled",
    "field-api_url",
    "field-token",
    "field-workspace_id",
    "field-project_id",
    "field-group_chat_mode",
    "field-group_chat_list",
    "field-private_chat_mode",
    "field-private_chat_list",
    "btn-test",
    "test-result",
    "toast",
]


def _page_html() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_page_exists_and_has_required_ids() -> None:
    html = _page_html()
    for element_id in REQUIRED_IDS:
        assert f'id="{element_id}"' in html, f"缺少元素 id: {element_id}"


def test_page_uses_supported_theme_api() -> None:
    """回归：bridge 没有 isDark / onThemeChange，必须用 getContext / onContext。"""
    html = _page_html()
    assert "onContext" in html
    assert "getContext" in html
    # 不允许出现对不存在的 bridge 成员的调用
    assert not re.search(r"\.onThemeChange\s*\(", html)
    assert not re.search(r"\bbridge\.isDark\b", html)
    # 暗色样式需同时支持 data-theme（AstrBot 写在 <html> 上）
    assert '[data-theme="dark"]' in html


def test_page_uses_bridge_relative_endpoints() -> None:
    html = _page_html()
    assert "apiGet('config'" in html
    assert "apiPost('actions/save_config'" in html
    assert "apiPost('actions/test_connection'" in html


def test_page_has_i18n_hooks() -> None:
    html = _page_html()
    assert "data-i18n=" in html
    assert "applyI18n" in html


def test_i18n_files_are_valid_and_aligned() -> None:
    zh = json.loads((I18N_DIR / "zh-CN.json").read_text(encoding="utf-8"))
    en = json.loads((I18N_DIR / "en-US.json").read_text(encoding="utf-8"))

    def flatten(node: dict, prefix: str = "") -> set[str]:
        keys: set[str] = set()
        for key, value in node.items():
            full = f"{prefix}{key}"
            if isinstance(value, dict):
                keys |= flatten(value, f"{full}.")
            else:
                keys.add(full)
        return keys

    assert flatten(zh) == flatten(en), "zh-CN 与 en-US 的键必须一一对应"
    # 页面里用到的键都必须存在，否则会静默回退到中文
    html = _page_html()
    for key in set(re.findall(r'data-i18n="([^"]+)"', html)):
        assert key in flatten(zh), f"i18n 缺少键: {key}"


def test_metadata_matches_page_and_changelog() -> None:
    meta = yaml.safe_load(METADATA.read_text(encoding="utf-8"))
    # 插件名必须是 AstrBot 认可的形式（生产环境即插件目录名）
    assert meta["name"].startswith("astrbot_plugin_")
    assert meta["astrbot_version"]

    pages = meta.get("pages") or []
    assert pages, "metadata.yaml 必须声明 pages"
    for page in pages:
        entry = ROOT / "pages" / page["name"] / page["entry_file"]
        assert entry.is_file(), f"页面入口不存在: {entry}"

    # CHANGELOG 首条版本应与 metadata 版本一致
    first = re.search(r"^##\s*\[([^\]]+)\]", CHANGELOG.read_text(encoding="utf-8"), re.M)
    assert first, "CHANGELOG 缺少版本条目"
    assert first.group(1) == meta["version"], (
        f"CHANGELOG({first.group(1)}) 与 metadata({meta['version']}) 版本不一致"
    )


def test_readme_documents_every_command() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for command in (
        "/multica help",
        "/multica status",
        "/multica issue create",
        "/multica workspace list",
        "/multica workspace select",
        "/multica workspace create",
        "/multica project list",
        "/multica project select",
        "/multica project create",
        "/multica inbox",
    ):
        assert command in readme, f"README 未收录指令: {command}"


def test_readme_images_use_absolute_urls() -> None:
    """AstrBot 直接用 markdown-it 渲染 README，且不做相对路径重写。

    相对路径（如 ``assets/banner.jpg``）会被解析到 Dashboard 域名下从而 404，
    因此图片与仓库内文档链接都必须写成绝对 URL。
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    relative_images = re.findall(r'<img[^>]*\ssrc="(?!https?://)([^"]+)"', readme)
    assert not relative_images, f"README 图片必须使用绝对 URL: {relative_images}"

    markdown_images = re.findall(r"!\[[^\]]*\]\((?!https?://)([^)]+)\)", readme)
    assert not markdown_images, f"README 图片必须使用绝对 URL: {markdown_images}"

    local_links = re.findall(r"\]\((?!https?://)([^)]+)\)", readme)
    assert not local_links, f"README 内部链接应使用绝对 URL: {local_links}"


def test_readme_avoids_internal_ticket_ids() -> None:
    """README 不应出现内部任务编号（形如 WS-12）。"""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert not re.search(r"\bWS-\d+", readme), "README 出现内部任务编号"
