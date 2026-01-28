import asyncio
import os
import sys

async def main():
    # Simple transparent binary proxy
    # We use a larger buffer for stdout to improve performance
    proc = await asyncio.create_subprocess_exec(
        "/opt/wordpress-mcp-server/venv/bin/python",
        "/opt/wordpress-mcp-server/mcp_server.py",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=sys.stderr
    )

    async def pipe_stdin():
        loop = asyncio.get_event_loop()
        while True:
            # Use read1 to return what is available immediately
            data = await loop.run_in_executor(None, sys.stdin.buffer.read1, 1024)
            if not data:
                break
            proc.stdin.write(data)
            await proc.stdin.drain()

    async def pipe_stdout():
        while True:
            # Read from process stdout
            data = await proc.stdout.read(4096)
            if not data:
                break
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()

    try:
        await asyncio.gather(pipe_stdin(), pipe_stdout())
    except Exception:
        pass
    finally:
        if proc.returncode is None:
            proc.terminate()
            await proc.wait()

if __name__ == "__main__":
    # Ensure stdout/stdin are in binary mode
    asyncio.run(main())