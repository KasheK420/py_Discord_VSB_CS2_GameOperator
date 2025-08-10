import asyncio
import a2s

async def get_info(host: str, port: int, timeout: float = 2.5):
    loop = asyncio.get_running_loop()
    addr = (host, port)
    return await asyncio.wait_for(loop.run_in_executor(None, a2s.info, addr), timeout)

async def get_players(host: str, port: int, timeout: float = 2.5):
    loop = asyncio.get_running_loop()
    addr = (host, port)
    return await asyncio.wait_for(loop.run_in_executor(None, a2s.players, addr), timeout)
