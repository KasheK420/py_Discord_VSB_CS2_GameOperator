import asyncio
from discord.ext import tasks
import discord
from utils.config import settings
from utils.source_query import get_info

async def _compose_presence():
    s = settings.CS2
    parts = []
    for key in ("surf", "bhop"):
        try:
            info = await get_info(s[key]["host"], s[key]["port"])
            parts.append(f"{key.capitalize()} {info.player_count}/{info.max_players}")
        except Exception:
            parts.append(f"{key.capitalize()} offline")
    return " | ".join(parts)

class PresenceTasks:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.loop.start()

    @tasks.loop(seconds=60)
    async def loop(self):
        try:
            txt = await _compose_presence()
            await self.bot.change_presence(activity=discord.Game(name=txt))
        except Exception:
            pass

    @loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()
