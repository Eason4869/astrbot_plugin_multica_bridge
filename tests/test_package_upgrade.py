import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

from test_upgrade import OLD

ROOT = Path(__file__).resolve().parents[1]


def test_install_zip_replaces_plugin_without_touching_old_config(tmp_path):
    path = ROOT / "scripts/build_package.py"
    assert path.is_file(), "Packaging tool not yet implemented"
    spec = importlib.util.spec_from_file_location("build_package", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    archive = module.build(tmp_path / "output")
    host = tmp_path / "astrbot/data"
    plugin_id = "astrbot_plugin_multica_bridge"
    data = host / "plugin_data" / plugin_id
    data.mkdir(parents=True)
    original = json.dumps(OLD).encode()
    (data / "config.json").write_bytes(original)
    plugins = host / "plugins"
    old_plugin = plugins / plugin_id
    old_plugin.mkdir(parents=True)
    (old_plugin / "main.py").write_text("# old version", encoding="utf-8")
    with ZipFile(archive) as package:
        assert all(name.startswith(plugin_id + "/") for name in package.namelist())
        assert not any(
            name.endswith("/config.json") or ".validation" in name or ".venv" in name
            for name in package.namelist()
        )
        package.extractall(plugins)
    assert (data / "config.json").read_bytes() == original
    spec = importlib.util.spec_from_file_location(
        "upgraded_config", old_plugin / "config.py"
    )
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    loaded = cfg.deep_merge(cfg.CONFIG_DEFAULTS, cfg.load_plugin_config(str(data)))
    assert loaded["api_url"] == OLD["api_url"]
    assert loaded["token"] == OLD["token"]
    assert loaded["work_mode_enabled"]
