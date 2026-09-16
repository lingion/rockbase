import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const CHROME_PLUGIN_ROOT = (() => {
  const candidates = [
    "${ROCKBASE_HOME}/.codex/plugins/cache/openai-bundled/chrome/26.519.81530",
    "${ROCKBASE_HOME}/.codex/plugins/cache/openai-bundled/Chrome/26.519.81530",
    "${ROCKBASE_HOME}/.codex/plugins/cache/openai-bundled/Chrome/0.1.7",
    "${ROCKBASE_HOME}/.codex/plugins/cache/openai-bundled/chrome/0.1.7",
  ];
  return candidates.find((candidate) => existsSync(candidate)) || candidates[0];
})();

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function browserClientUrl() {
  return pathToFileURL(path.join(CHROME_PLUGIN_ROOT, "scripts/browser-client.mjs")).href;
}

export async function setupChromeRuntime() {
  const runtimeModule = await import(browserClientUrl());
  const setupRuntime = runtimeModule.setupBrowserRuntime || runtimeModule.setupAtlasRuntime;
  if (typeof setupRuntime !== "function") {
    throw new Error("Chrome browser-client runtime export not found");
  }
  await setupRuntime({ globals: globalThis });
}

export async function listAvailableBrowsers() {
  if (!globalThis.agent) {
    await setupChromeRuntime();
  }
  return globalThis.agent.browsers.list();
}

export async function ensureChromeExtensionBrowser() {
  try {
    if (globalThis.browser) {
      await globalThis.browser.nameSession("🔌 Chrome bootstrap");
      return globalThis.browser;
    }
  } catch {
    globalThis.browser = null;
  }

  const failures = [];
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    globalThis.browser = null;
    globalThis.agent = null;
    try {
      await setupChromeRuntime();
      globalThis.browser = await globalThis.agent.browsers.get("extension");
      await globalThis.browser.nameSession("🔌 Chrome bootstrap");
      return globalThis.browser;
    } catch (error) {
      const available = (await globalThis.agent?.browsers?.list?.().catch(() => [])) || [];
      failures.push({
        attempt,
        available: available.map((item) => ({ name: item.name, type: item.type })),
        error: String(error?.message || error || ""),
      });
      await sleep(attempt === 1 ? 500 : 2000);
    }
  }

  throw new Error(
    [
      "Codex Chrome extension backend is not available.",
      "Open @Chrome, confirm the plugin is Connected, then retry bootstrap.",
      `attempts=${JSON.stringify(failures)}`,
    ].join(" ")
  );
}

export async function runCodexChromeBootstrap(options = {}) {
  const {
    probeUrl = "https://example.com/",
    keepProbeTab = false,
  } = options;

  const browser = await ensureChromeExtensionBrowser();
  const availableBrowsers = (await globalThis.agent.browsers.list().catch(() => [])) || [];
  const tab = await browser.tabs.new();
  let probe = { ready: false, title: "", url: "" };

  try {
    await tab.goto(probeUrl);
    await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 15000 });
    const title = await tab.title();
    const url = await tab.url();
    const body = await tab.playwright.locator("body").innerText({ timeoutMs: 5000 }).catch(() => "");
    probe = {
      ready: /Example Domain/i.test(title || "") || /Example Domain/i.test(body || ""),
      title: title || "",
      url: url || "",
      bodySnippet: String(body || "").slice(0, 160),
    };
  } finally {
    await browser.tabs.finalize({
      keep: keepProbeTab ? [{ status: "handoff", tab }] : [],
    });
  }

  if (!probe.ready) {
    throw new Error(`Chrome bootstrap probe failed for ${probeUrl}`);
  }

  return {
    ready: true,
    browserType: "extension",
    probe,
    availableBrowsers: availableBrowsers.map((item) => ({ name: item.name, type: item.type })),
    scriptDir: SCRIPT_DIR,
  };
}
