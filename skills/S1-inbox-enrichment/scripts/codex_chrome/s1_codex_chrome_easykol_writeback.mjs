import fs from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { execFile as execFileCb } from "node:child_process";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { ensureChromeExtensionBrowser, runCodexChromeBootstrap } from "./s1_codex_chrome_bootstrap.mjs";

const execFile = promisify(execFileCb);

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = path.resolve(SCRIPT_DIR, "..", "..");
const PROJECT_ROOT = (() => {
  const derived = path.resolve(SKILL_ROOT, "..", "..");
  if (derived.endsWith(`${path.sep}.agent`)) {
    return derived.slice(0, -`${path.sep}.agent`.length);
  }
  return derived.includes(`${path.sep}.agent${path.sep}`)
    ? derived.replace(`${path.sep}.agent`, "")
    : derived;
})();

const REQUIRED_COLUMNS = ["账号链接", "联系方式", "联系方式备注"];
const DEFAULT_WAIT_MS = 18000;
const DEFAULT_RETRY_WAIT_MS = 8000;
const PANEL_CROP_RATIO = { x: 0.725, y: 0.028, width: 0.275, height: 0.361 };
const EMAIL_CROP_RATIO = { x: 0.741, y: 0.108, width: 0.188, height: 0.083 };
const TESSERACT_PATH = existsSync("/opt/homebrew/bin/tesseract") ? "/opt/homebrew/bin/tesseract" : "tesseract";

function todayString() {
  return new Date().toISOString().slice(0, 10);
}

function nowStamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

function ensureArray(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  return String(value)
    .split(",")
    .map((chunk) => chunk.trim())
    .filter(Boolean);
}

function parseRowsSpec(raw) {
  const values = [];
  for (const chunk of ensureArray(raw)) {
    if (chunk.includes("-")) {
      const [start, end] = chunk.split("-", 2).map((v) => Number(v));
      for (let row = start; row <= end; row += 1) values.push(row);
    } else {
      values.push(Number(chunk));
    }
  }
  return [...new Set(values.filter((v) => Number.isFinite(v) && v >= 2))];
}

function slugify(value) {
  return String(value || "")
    .replace(/[^A-Za-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 60) || "row";
}

function decodeCsvCell(raw) {
  if (raw.startsWith('"') && raw.endsWith('"')) {
    return raw.slice(1, -1).replace(/""/g, '"');
  }
  return raw;
}

function encodeCsvCell(raw) {
  const value = String(raw ?? "");
  if (/[",\n\r]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];

    if (inQuotes) {
      if (ch === '"' && next === '"') {
        cell += '"';
        i += 1;
      } else if (ch === '"') {
        inQuotes = false;
      } else {
        cell += ch;
      }
      continue;
    }

    if (ch === '"') {
      inQuotes = true;
      continue;
    }
    if (ch === ",") {
      row.push(cell);
      cell = "";
      continue;
    }
    if (ch === "\n") {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
      continue;
    }
    if (ch === "\r") continue;
    cell += ch;
  }

  row.push(cell);
  rows.push(row);
  return rows;
}

function stringifyCsv(rows) {
  return rows.map((row) => row.map(encodeCsvCell).join(",")).join("\n");
}

function extractPanelValueLines(panel) {
  return panel
    .split("\n")
    .map((line) => line.trim())
    .map((line) => {
      const genericMatch = line.match(/^- generic: ?(?:"([^"]+)"|(.*))$/);
      if (genericMatch) return (genericMatch[1] ?? genericMatch[2] ?? "").trim();
      const textMatch = line.match(/^- text: ?(?:"([^"]+)"|(.*))$/);
      if (textMatch) return (textMatch[1] ?? textMatch[2] ?? "").trim();
      return null;
    })
    .filter(Boolean);
}

function buildSplitEmails(values) {
  const domains = values
    .map((value, index) => ({ value: value.replace(/^"|"$/g, "").trim(), index }))
    .filter(({ value }) => /^@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(value));

  const emails = [];
  for (const { value: domain, index: domainIndex } of domains) {
    for (let offset = 1; offset <= 2; offset += 1) {
      const localIndex = domainIndex - offset;
      if (localIndex < 0) continue;
      const local = values[localIndex].replace(/^"|"$/g, "").trim();
      if (/^[A-Za-z0-9._%+-]{2,}$/.test(local)) {
        emails.push(`${local}${domain}`);
        break;
      }
    }
  }
  return [...new Set(emails)];
}

function extractEmails(text) {
  return [...new Set(String(text || "").match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi) || [])];
}

async function loadCsv(csvPath) {
  const raw = await fs.readFile(csvPath, "utf8");
  const hasBom = raw.charCodeAt(0) === 0xfeff;
  const rows = parseCsv(hasBom ? raw.slice(1) : raw);
  const header = rows[0];
  const records = rows.slice(1).map((row, index) => {
    const obj = {};
    header.forEach((key, colIndex) => {
      obj[key] = decodeCsvCell(row[colIndex] ?? "");
    });
    obj.__rowNumber = index + 2;
    return obj;
  });
  return { hasBom, rows, header, records };
}

async function saveCsv(csvPath, header, records, hasBom) {
  const rows = [
    header,
    ...records.map((record) => header.map((key) => record[key] ?? "")),
  ];
  const text = stringifyCsv(rows);
  await fs.writeFile(csvPath, `${hasBom ? "\ufeff" : ""}${text}`, "utf8");
}

function extractEmailFromPanel(snapshot) {
  const idx = Math.max(snapshot.indexOf("generic: 邮箱"), snapshot.indexOf("邮箱"));
  const endCandidates = ['generic: 发邮件', 'button "发送邮件', "generic: 预估报价"];
  let end = -1;
  for (const token of endCandidates) {
    const pos = snapshot.indexOf(token, idx >= 0 ? idx : 0);
    if (pos >= 0 && (end < 0 || pos < end)) end = pos;
  }
  const panel = idx >= 0 ? snapshot.slice(idx, end > idx ? end : idx + 1500) : "";
  const directMatches = extractEmails(panel);
  const panelValues = extractPanelValueLines(panel);
  const splitMatches = buildSplitEmails(panelValues);
  return {
    emails: [...new Set([...directMatches, ...splitMatches])],
    panel,
  };
}

async function runPythonCrop(inputPath, outputPath, ratio) {
  const script = [
    "from PIL import Image",
    "import sys",
    "src, dst, x, y, w, h = sys.argv[1:]",
    "img = Image.open(src)",
    "width, height = img.size",
    "left = max(0, min(width - 1, int(round(width * float(x)))))",
    "top = max(0, min(height - 1, int(round(height * float(y)))))",
    "crop_w = max(1, int(round(width * float(w))))",
    "crop_h = max(1, int(round(height * float(h))))",
    "right = min(width, left + crop_w)",
    "bottom = min(height, top + crop_h)",
    "cropped = img.crop((left, top, right, bottom))",
    "scaled = cropped.resize((max(1, cropped.size[0] * 3), max(1, cropped.size[1] * 3)))",
    "scaled.save(dst)",
  ].join("\n");
  await execFile("python3", [
    "-c",
    script,
    inputPath,
    outputPath,
    String(ratio.x),
    String(ratio.y),
    String(ratio.width),
    String(ratio.height),
  ]);
}

async function runTesseract(imagePath, mode) {
  const args = [imagePath, "stdout"];
  if (mode === "email") {
    args.push("--psm", "7", "-c", "tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@._-");
  } else {
    args.push("--psm", "6");
  }
  const { stdout } = await execFile(TESSERACT_PATH, args);
  return String(stdout || "").trim();
}

function panelLooksVisible(panelOcrText) {
  const text = String(panelOcrText || "");
  if (text.length >= 24) return true;
  return /\$\d+|\d+K|\d+%|CPM|ER|Latest|Popular|邮箱|发邮件/i.test(text);
}

function emailCropLooksEmpty(emailOcrText) {
  const text = String(emailOcrText || "").replace(/\s+/g, "");
  if (!text) return true;
  return /^(输入邮箱地址|inputemail|emailaddress)$/i.test(text);
}

async function writeBackup(csvPath) {
  const backupDir = path.join(PROJECT_ROOT, "Agency", "list-bak", todayString());
  await fs.mkdir(backupDir, { recursive: true });
  const backupPath = path.join(backupDir, `${path.basename(csvPath)}_bak_${nowStamp()}.csv`);
  await fs.copyFile(csvPath, backupPath);
  return backupPath;
}

function selectTargetRecords(records, rowNumbers) {
  if (rowNumbers.length) {
    const set = new Set(rowNumbers);
    return records.filter((record) => set.has(record.__rowNumber));
  }
  return records.filter((record) => {
    if (String(record["联系方式"] || "").trim()) return false;
    const note = String(record["联系方式备注"] || "").trim();
    return note !== "EasyKOL获取" && note !== "EasyKOL无法获取";
  });
}

async function writeReviewArtifacts(outDir, results) {
  await fs.mkdir(outDir, { recursive: true });
  const stamp = nowStamp();
  const jsonPath = path.join(outDir, `codex_chrome_easykol_review_${stamp}.json`);
  const mdPath = path.join(outDir, `codex_chrome_easykol_review_${stamp}.md`);
  await fs.writeFile(jsonPath, JSON.stringify(results, null, 2), "utf8");
  const lines = [
    `processed: ${results.length}`,
    ...results.map((result) => {
      const email = result.email || "";
      return `- row ${result.row}: ${result.name} | ${result.status} | ${result.source || ""} | ${email} | ${result.note}`;
    }),
  ];
  await fs.writeFile(mdPath, `${lines.join("\n")}\n`, "utf8");
  return { jsonPath, mdPath };
}

async function captureVisibleArtifacts(tab, basePathNoExt, keepVisible) {
  const visiblePath = `${basePathNoExt}_visible.png`;
  const image = await tab.screenshot({ fullPage: false });
  const imageBytes =
    typeof image?.toBase64 === "function"
      ? Buffer.from(image.toBase64(), "base64")
      : ArrayBuffer.isView(image)
        ? Buffer.from(image)
      : Buffer.isBuffer(image)
        ? image
        : image?.bytes
          ? Buffer.from(image.bytes)
          : Buffer.from(image?.data || "", "base64");
  await fs.writeFile(visiblePath, imageBytes);
  const panelPath = `${basePathNoExt}_panel.png`;
  const emailPath = `${basePathNoExt}_email.png`;
  await runPythonCrop(visiblePath, panelPath, PANEL_CROP_RATIO);
  await runPythonCrop(visiblePath, emailPath, EMAIL_CROP_RATIO);
  if (!keepVisible) {
    await fs.unlink(visiblePath).catch(() => {});
  }
  return { visiblePath: keepVisible ? visiblePath : "", panelPath, emailPath };
}

async function readVisiblePanelEmail(tab, record, outDir, options) {
  const {
    captureEvidence,
    retryWaitMs,
  } = options;
  const base = `${String(record.__rowNumber).padStart(4, "0")}_${slugify(record["频道/作者名称"] || record["账号链接"])}`;
  let lastAttempt = null;

  for (let attempt = 1; attempt <= 3; attempt += 1) {
    const basePathNoExt = path.join(outDir, `${base}_fallback_attempt${attempt}`);
    const artifacts = await captureVisibleArtifacts(tab, basePathNoExt, captureEvidence);
    const panelOcr = await runTesseract(artifacts.panelPath, "panel").catch(() => "");
    const emailOcr = await runTesseract(artifacts.emailPath, "email").catch(() => "");
    const combinedEmails = extractEmails([emailOcr, panelOcr].join("\n"));
    const panelVisible = panelLooksVisible(panelOcr);
    const emailEmpty = emailCropLooksEmpty(emailOcr);

    await fs.writeFile(`${basePathNoExt}_panel_ocr.txt`, panelOcr, "utf8");
    await fs.writeFile(`${basePathNoExt}_email_ocr.txt`, emailOcr, "utf8");

    lastAttempt = {
      attempt,
      panelPath: artifacts.panelPath,
      emailPath: artifacts.emailPath,
      panelOcrPath: `${basePathNoExt}_panel_ocr.txt`,
      emailOcrPath: `${basePathNoExt}_email_ocr.txt`,
      panelOcr,
      emailOcr,
      emails: combinedEmails,
      panelVisible,
      emailEmpty,
    };

    if (combinedEmails[0]) {
      return {
        status: "hit",
        source: "visible_ocr",
        email: combinedEmails[0],
        note: "EasyKOL获取",
        fallback: lastAttempt,
      };
    }

    if (attempt < 3 && (!panelVisible || !emailEmpty)) {
      await tab.playwright.waitForTimeout(retryWaitMs);
      continue;
    }

    if (attempt < 3 && panelVisible && emailEmpty) {
      await tab.playwright.waitForTimeout(retryWaitMs);
      continue;
    }
  }

  if (lastAttempt?.panelVisible && lastAttempt?.emailEmpty) {
    return {
      status: "no_email",
      source: "visible_ocr",
      email: "",
      note: "EasyKOL无法获取",
      fallback: lastAttempt,
    };
  }

  return {
    status: "retry",
    source: "visible_ocr",
    email: "",
    note: "EasyKOL页面错误待重试",
    fallback: lastAttempt,
  };
}

export async function runCodexChromeEasykolWriteback(options) {
  const {
    csvPath,
    rows = "",
    write = false,
    skipBackup = false,
    captureEvidence = true,
    screenshotDir = "",
    waitMs = DEFAULT_WAIT_MS,
    retryWaitMs = DEFAULT_RETRY_WAIT_MS,
    runBootstrapProbe = true,
    skipDomPhase = false,
  } = options;

  if (!csvPath) throw new Error("csvPath is required");

  const resolvedCsvPath = path.resolve(csvPath);
  const parsedRows = parseRowsSpec(rows);
  const { hasBom, header, records } = await loadCsv(resolvedCsvPath);
  for (const column of REQUIRED_COLUMNS) {
    if (!header.includes(column)) {
      throw new Error(`CSV missing required column: ${column}`);
    }
  }

  const targets = selectTargetRecords(records, parsedRows);
  const outDir = path.join(PROJECT_ROOT, "workbench", todayString(), "codex_chrome_easykol_writeback");
  const evidenceDir = screenshotDir || path.join(outDir, "evidence");
  await fs.mkdir(outDir, { recursive: true });
  await fs.mkdir(evidenceDir, { recursive: true });

  let backupPath = "";
  if (write && !skipBackup) {
    backupPath = await writeBackup(resolvedCsvPath);
  }

  const bootstrap = runBootstrapProbe
    ? await runCodexChromeBootstrap({ probeUrl: "https://example.com/", keepProbeTab: false })
    : { ready: true };
  const browser = await ensureChromeExtensionBrowser();
  const tab = await browser.tabs.new();
  const results = [];

  try {
    for (const record of targets) {
      const result = {
        row: record.__rowNumber,
        name: record["频道/作者名称"] || "",
        url: record["账号链接"] || "",
        email: "",
        note: "",
        status: "",
        source: "",
        domPanelTextPath: "",
        panelImagePath: "",
        emailImagePath: "",
        panelOcrPath: "",
        emailOcrPath: "",
      };

      if (String(record["联系方式"] || "").trim()) {
        result.status = "skipped_existing_contact";
        result.note = record["联系方式备注"] || "";
        results.push(result);
        continue;
      }

      if (!result.url) {
        result.status = "retry";
        result.note = "EasyKOL页面错误待重试";
        results.push(result);
        continue;
      }

      try {
        let navigationError = null;
        await tab.goto(result.url).catch((error) => {
          navigationError = error;
        });
        await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 30000 }).catch(() => {});
        await tab.playwright.waitForTimeout(waitMs);

        if (navigationError) {
          const currentUrl = await tab.url().catch(() => "");
          const currentTitle = await tab.title().catch(() => "");
          const pageLooksLoaded =
            (currentUrl && currentUrl.startsWith("https://www.instagram.com/")) ||
            /instagram/i.test(currentTitle || "");
          if (!pageLooksLoaded) {
            throw navigationError;
          }
        }

        const snapshot = await tab.playwright.domSnapshot();
        const domResult = extractEmailFromPanel(snapshot);
        const base = `${String(record.__rowNumber).padStart(4, "0")}_${slugify(record["频道/作者名称"] || record["账号链接"])}`;
        const domPanelTextPath = path.join(outDir, `${base}_dom_panel.txt`);
        await fs.writeFile(domPanelTextPath, domResult.panel || "", "utf8");
        result.domPanelTextPath = domPanelTextPath;

        const domEmail = skipDomPhase ? "" : (domResult.emails[0] || "");
        if (domEmail) {
          result.email = domEmail;
          result.note = "EasyKOL获取";
          result.status = "hit";
          result.source = "dom";
          if (write) {
            record["联系方式"] = domEmail;
            record["联系方式备注"] = "EasyKOL获取";
          }
        } else {
          const fallback = await readVisiblePanelEmail(tab, record, evidenceDir, {
            captureEvidence,
            retryWaitMs,
          });
          result.email = fallback.email;
          result.note = fallback.note;
          result.status = fallback.status;
          result.source = fallback.source;
          result.panelImagePath = fallback.fallback?.panelPath || "";
          result.emailImagePath = fallback.fallback?.emailPath || "";
          result.panelOcrPath = fallback.fallback?.panelOcrPath || "";
          result.emailOcrPath = fallback.fallback?.emailOcrPath || "";
          if (write && fallback.status === "hit") {
            record["联系方式"] = fallback.email;
            record["联系方式备注"] = "EasyKOL获取";
          }
          if (write && fallback.status === "no_email") {
            record["联系方式备注"] = "EasyKOL无法获取";
          }
        }
      } catch (error) {
        result.status = "retry";
        result.note = "EasyKOL页面错误待重试";
        result.error = String(error);
      }

      results.push(result);
    }
  } finally {
    await browser.tabs.finalize({ keep: [] });
  }

  if (write) {
    await saveCsv(resolvedCsvPath, header, records, hasBom);
  }

  const reviewArtifacts = await writeReviewArtifacts(outDir, results);
  return {
    csvPath: resolvedCsvPath,
    processed: results.length,
    write,
    backupPath,
    bootstrap,
    outDir,
    evidenceDir,
    reviewArtifacts,
    results,
  };
}
