"""dt-timemachine, week 1: transparent passthrough MCP proxy with call logging.

Supports two upstream transports:
  UPSTREAM_TRANSPORT=stdio  (default) -> spawn a local MCP server (fake upstream, or npx)
  UPSTREAM_TRANSPORT=http             -> connect to Dynatrace Remote MCP Server over HTTP

For http mode:
  DT_MCP_URL         full MCP endpoint, e.g.
                     https://<env>.apps.dynatrace.com/platform-reserved/mcp-gateway/v0.1/servers/dynatrace-mcp/mcp
  DT_PLATFORM_TOKEN  platform token (dt0s16...)
"""
import asyncio
import json
import os
import shlex
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx2
from mcp import ClientSession, types
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client   # v2 name
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server


def log(msg: str) -> None:
    print(f"[dt-timemachine] {msg}", file=sys.stderr, flush=True)


# --------------------------------------------------------------------------
# Hook points (week 2+). Keep them pure and easy to test.
# --------------------------------------------------------------------------
def transform_request(name: str, arguments: dict | None):
    """Week 2: clamp DQL time ranges to the incident cutoff here.
    Return (name, arguments); raise ValueError to reject a call."""
    return name, arguments


def transform_response(name: str, arguments: dict | None, result: types.CallToolResult):
    """Week 2: hide events/problems after the cutoff. Week 4: mutations."""
    return result


# --------------------------------------------------------------------------
# JSONL call log
# --------------------------------------------------------------------------
class CallLog:
    def __init__(self, directory: str):
        Path(directory).mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.path = Path(directory) / f"run-{stamp}.jsonl"
        self.seq = 0

    def write(self, record: dict) -> None:
        self.seq += 1
        record = {"seq": self.seq, "ts": datetime.now(timezone.utc).isoformat(), **record}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def split_args(text: str, windows: bool | None = None) -> list[str]:
    if windows is None:
        windows = os.name == "nt"
    if not windows:
        return shlex.split(text)
    out = []
    for tok in shlex.split(text, posix=False):
        if len(tok) > 1 and tok[0] == tok[-1] and tok[0] in "\"'":
            tok = tok[1:-1]
        out.append(tok)
    return out


def upstream_params() -> StdioServerParameters:
    cmd = os.environ.get("UPSTREAM_CMD", "npx")
    args = split_args(
        os.environ.get("UPSTREAM_ARGS", "-y @dynatrace-oss/dynatrace-mcp-server")
    )
    return StdioServerParameters(command=cmd, args=args, env=None)


def upstream_transport() -> str:
    return os.environ.get("UPSTREAM_TRANSPORT", "stdio").lower()


# --------------------------------------------------------------------------
# Uniform async context manager for both transports
# --------------------------------------------------------------------------
@asynccontextmanager
async def connect_upstream():
    if upstream_transport() == "http":
        url = os.environ.get("DT_MCP_URL", "").strip()
        token = os.environ.get("DT_PLATFORM_TOKEN", "").strip()
        if not url or not token:
            raise RuntimeError(
                "DT_MCP_URL and DT_PLATFORM_TOKEN are required when UPSTREAM_TRANSPORT=http"
            )
        log(f"connecting to remote MCP over HTTP: {url}")
        # v2: headers and timeouts live on the httpx2.AsyncClient, not on the transport
        async with httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx2.Timeout(30.0, read=300.0),
        ) as http_client:
            async with streamable_http_client(url, http_client=http_client) as (read, write):
                yield read, write
    else:
        log("connecting to local MCP over stdio")
        async with stdio_client(upstream_params(), errlog=sys.stderr) as (read, write):
            yield read, write


async def main() -> None:
    calls = CallLog(os.environ.get("RUN_LOG_DIR", "runs"))
    log(f"logging calls to {calls.path}")

    async with connect_upstream() as (up_read, up_write):
        async with ClientSession(up_read, up_write) as upstream:
            await upstream.initialize()
            log("connected to upstream MCP server")

            async def on_list_tools(ctx, params):
                result = await upstream.list_tools(params=params)
                calls.write({"event": "list_tools", "tools": [t.name for t in result.tools]})
                return result

            async def on_call_tool(ctx, params: types.CallToolRequestParams):
                started = time.monotonic()
                name, args = params.name, params.arguments
                try:
                    name, args = transform_request(name, args)
                    result = await upstream.call_tool(name, args)
                    result = transform_response(name, args, result)
                except Exception as exc:
                    calls.write({
                        "event": "call_tool", "tool": params.name,
                        "arguments": params.arguments, "error": repr(exc),
                        "ms": round((time.monotonic() - started) * 1000),
                    })
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=f"proxy error: {exc}")],
                        is_error=True,
                    )
                calls.write({
                    "event": "call_tool", "tool": params.name,
                    "arguments": params.arguments, "forwarded_arguments": args,
                    "is_error": getattr(result, "is_error", False),
                    "response": result.model_dump(mode="json", exclude_none=True),
                    "ms": round((time.monotonic() - started) * 1000),
                })
                return result

            server = Server(
                "dt-timemachine",
                on_list_tools=on_list_tools,
                on_call_tool=on_call_tool,
            )
            async with stdio_server() as (read, write):
                await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())