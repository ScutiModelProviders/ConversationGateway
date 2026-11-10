"""The options the admin page can change. A saved value wins over the environment value shown as default."""
from __future__ import annotations

from src.config import Settings
from src.runtime import Config, LiveSettings, Setting

FIELDS = {  # Settings attribute -> (setting key, conversion)
    "max_messages": ("max_messages", int),
    "max_text": ("max_text", int),
    "max_tools": ("max_tools", int),
    "max_images": ("max_images", int),
    "max_image_mb": ("max_image_mb", int),
    "max_inflight": ("max_inflight", int),
}


def schema(base: Settings) -> list[Setting]:
    return [
        Setting("max_messages", "Most messages per request", "int", base.max_messages, minimum=1, maximum=5000),
        Setting("max_text", "Longest text block (characters)", "int", base.max_text, minimum=1, maximum=5000000),
        Setting("max_tools", "Most tools per request", "int", base.max_tools, minimum=1, maximum=1024),
        Setting("max_images", "Most images per request", "int", base.max_images, minimum=1, maximum=200),
        Setting("max_image_mb", "Largest image (MiB)", "int", base.max_image_mb, minimum=1, maximum=64),
        Setting("max_inflight", "Chats at once", "int", base.max_inflight, minimum=1, maximum=256,
                help="More than this many at once get 429 with Retry-After."),
        Setting("data_path", "Data folder", "text", "", restart=True,
                help=f"Where stored data goes. Empty = {base.state_dir}. Applies after a restart; files already stored are not moved."),
    ]


def make_config(base: Settings) -> Config | None:
    """None, so nothing is changeable at run time, unless SERVICE_ADMIN_PASSWORD is set."""
    return Config(base.state_dir / "settings.json", schema(base)) if base.admin_password else None


def live(base: Settings, config: Config | None):
    return LiveSettings(base, config, FIELDS) if config else base
