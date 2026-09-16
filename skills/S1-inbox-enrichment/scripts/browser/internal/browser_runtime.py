from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path

from playwright.async_api import async_playwright


CDP_VERSION_URL = "http://127.0.0.1:9222/json/version"
DEFAULT_CHROME_PORT = 9223
LAUNCHER_CANDIDATES = [
    Path("${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/04 🛜 Net/ag-omni-chrome/scripts/launcher_omni_chrome.sh"),
]
DEFAULT_CHROME_CANDIDATES = [
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


async def get_browser_context():
    try:
        await ensure_omni_running()
        playwright = await async_playwright().start()
        ws_url = subprocess.check_output(["curl", "-s", CDP_VERSION_URL]).decode("utf-8")
        ws_endpoint = json.loads(ws_url)["webSocketDebuggerUrl"]
        browser = await playwright.chromium.connect_over_cdp(ws_endpoint)
        context = browser.contexts[0]
        return playwright, browser, context
    except Exception:
        # Fall back to a debuggable default Chrome instance when Omni is unavailable.
        return await get_default_chrome_context()


async def get_default_chrome_context(port: int = DEFAULT_CHROME_PORT):
    cdp_version_url = f"http://127.0.0.1:{port}/json/version"
    await ensure_default_chrome_debuggable(port=port)
    playwright = await async_playwright().start()
    ws_url = subprocess.check_output(["curl", "-s", cdp_version_url]).decode("utf-8")
    ws_endpoint = json.loads(ws_url)["webSocketDebuggerUrl"]
    browser = await playwright.chromium.connect_over_cdp(ws_endpoint)
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    return playwright, browser, context


async def ensure_omni_running():
    if _cdp_alive():
        return
    launcher = _find_launcher()
    if launcher is None:
        raise RuntimeError("未发现可用的 Omni-Chrome launcher，且 9222 当前不可用")
    subprocess.Popen(
        ["bash", str(launcher)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(20):
        if _cdp_alive():
            return
        await asyncio.sleep(1)
    raise RuntimeError("Omni-Chrome 未能在 9222 启动")


async def ensure_default_chrome_debuggable(port: int = DEFAULT_CHROME_PORT) -> dict[str, str]:
    cdp_version_url = f"http://127.0.0.1:{port}/json/version"
    if _cdp_alive(cdp_version_url):
        return {"mode": "connected_existing", "port": str(port)}

    chrome_binary = _find_default_chrome_binary()
    if chrome_binary is None:
        raise RuntimeError("未发现可用的 Google Chrome.app，无法启动默认 Chrome 调试实例")

    subprocess.Popen(
        [
            str(chrome_binary),
            f"--remote-debugging-port={port}",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=_chrome_env(),
    )
    for _ in range(20):
        if _cdp_alive(cdp_version_url):
            return {"mode": "launched_primary_profile", "port": str(port)}
        await asyncio.sleep(1)
    raise RuntimeError(f"默认 Chrome 未能在 {port} 启动远程调试")


def _cdp_alive(version_url: str = CDP_VERSION_URL) -> bool:
    try:
        output = subprocess.check_output(["curl", "-s", version_url], stderr=subprocess.DEVNULL).decode("utf-8")
        data = json.loads(output)
        return bool(data.get("webSocketDebuggerUrl"))
    except Exception:
        return False


def _find_launcher() -> Path | None:
    for candidate in LAUNCHER_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _find_default_chrome_binary() -> Path | None:
    for candidate in DEFAULT_CHROME_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _chrome_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("LC_ALL", "en_US.UTF-8")
    env.setdefault("LANG", "en_US.UTF-8")
    return env
