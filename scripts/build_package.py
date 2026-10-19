"""Build a source-only plugin ZIP; deployment data is never included."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ID = "astrbot_plugin_multica_bridge"
FILES = (
    "main.py",
    "config.py",
    "web_api.py",
    "multica_client.py",
    "nl_control.py",
    "chat_client.py",
    "session_store.py",
    "work_mode.py",
    "reply_worker.py",
    "astrbot_compat.py",
    "work_mode_integration.py",
    "metadata.yaml",
    "requirements.txt",
    "config.example.json",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "logo.svg",
    "logo.png",
)


def build(output: Path | None = None) -> Path:
    output = output or ROOT / "dist"
    output.mkdir(parents=True, exist_ok=True)
    version = next(
        line.split(":", 1)[1].strip()
        for line in (ROOT / "metadata.yaml").read_text(encoding="utf-8").splitlines()
        if line.startswith("version:")
    )
    archive = output / f"{PLUGIN_ID}-{version}.zip"
    files = [ROOT / name for name in FILES]
    for name in ("pages", ".astrbot-plugin", "assets"):
        files.extend(path for path in (ROOT / name).rglob("*") if path.is_file())
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as package:
        for file in sorted(files):
            package.write(file, PLUGIN_ID + "/" + file.relative_to(ROOT).as_posix())
    return archive


if __name__ == "__main__":
    print(build())
