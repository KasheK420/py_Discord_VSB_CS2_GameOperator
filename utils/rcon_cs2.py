import asyncio
from rcon.source import Client

async def rcon_exec(host: str, port: int, password: str, command: str, timeout: float = 3.0) -> str:
    loop = asyncio.get_running_loop()
    def run():
        with Client(host, port, passwd=password, timeout=timeout) as c:
            return c.run(command)
    return await loop.run_in_executor(None, run)
