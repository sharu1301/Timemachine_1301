"""Run: python tests/test_passthrough.py  (from the dt-timemachine folder)
Starts the proxy in front of the fake upstream and checks passthrough + logging."""
import asyncio, glob, json, os, sys, tempfile
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


async def main():
    logdir = tempfile.mkdtemp()
    env = {
        "UPSTREAM_CMD": sys.executable,
        "UPSTREAM_ARGS": '"' + os.path.join(HERE, "fake_upstream.py") + '"',  # quoted: paths may contain spaces
        "RUN_LOG_DIR": logdir,
    }
    params = StdioServerParameters(
        command=sys.executable, args=[os.path.join(ROOT, "proxy.py")], env=env
    )
    async with stdio_client(params, errlog=sys.stderr) as (r, w):  # show proxy errors
        async with ClientSession(r, w) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert [t.name for t in tools.tools] == ["execute_dql"], tools
            res = await session.call_tool("execute_dql", {"query": "fetch logs | limit 1"})
            text = res.content[0].text
            assert "fetch logs | limit 1" in text, text
    lines = [json.loads(l) for l in open(glob.glob(os.path.join(logdir, "*.jsonl"))[0])]
    events = [l["event"] for l in lines]
    assert events == ["list_tools", "call_tool"], events
    assert lines[1]["arguments"] == {"query": "fetch logs | limit 1"}
    print("PASS: passthrough works and", len(lines), "calls were logged")


asyncio.run(main())