import os
from dataclasses import dataclass
from typing import Sequence

def _csv_ints(s: str | None) -> list[int]:
    if not s:
        return []
    return [int(x.strip()) for x in s.split(",") if x.strip().isdigit()]

@dataclass
class Settings:
    # Discord
    DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
    DISCORD_GUILD_ID: int = int(os.getenv("DISCORD_GUILD_ID", "0"))
    PANEL_CHANNEL_ID: int = int(os.getenv("DISCORD_PANEL_CHANNEL_ID", "0"))
    DISCORD_ADMIN_ROLE_IDS: str = os.getenv("DISCORD_ADMIN_ROLE_IDS", "")
    DISCORD_MOD_ROLE_IDS: str = os.getenv("DISCORD_MOD_ROLE_IDS", "")

    # DB
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_USER: str = os.getenv("DB_USER", "vsb")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "vsbpass")
    DB_NAME: str = os.getenv("DB_NAME", "vsb_bot")

    # HTTP
    HTTP_HOST: str = os.getenv("HTTP_HOST", "0.0.0.0")
    HTTP_PORT: int = int(os.getenv("HTTP_PORT", "8080"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # CS2
    CS2: dict = None  # filled below

    def roles_from_csv(self, s: str) -> Sequence[int]:
        return _csv_ints(s)

settings = Settings()

settings.CS2 = {
    "surf": {
        "host": os.getenv("CS2_SURF_HOST", "127.0.0.1"),
        "port": int(os.getenv("CS2_SURF_PORT", "27015")),
        "rcon_host": os.getenv("CS2_SURF_RCON_HOST", "127.0.0.1"),
        "rcon_port": int(os.getenv("CS2_SURF_RCON_PORT", "27015")),
        "rcon_pass": os.getenv("CS2_SURF_RCON_PASSWORD", ""),
        "server_pass": os.getenv("CS2_SURF_PASSWORD", ""),
    },
    "bhop": {
        "host": os.getenv("CS2_BHOP_HOST", "127.0.0.1"),
        "port": int(os.getenv("CS2_BHOP_PORT", "27016")),
        "rcon_host": os.getenv("CS2_BHOP_RCON_HOST", "127.0.0.1"),
        "rcon_port": int(os.getenv("CS2_BHOP_RCON_PORT", "27016")),
        "rcon_pass": os.getenv("CS2_BHOP_RCON_PASSWORD", ""),
        "server_pass": os.getenv("CS2_BHOP_PASSWORD", ""),
    },
}
