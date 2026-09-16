const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

async function main() {
    const accountIds = [
        "Addison Jarman",
        "ThePptPro",
        "mohammadfraz",
        "estebandiba",
        "studywithnali",
        "AI News Central",
        "Mike Moore",
        "Smart & Easy",
        "joshualarosa.ai"
    ];

    const auditDir = "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/Proj-Skywork/ag-skywalk-查重/audit_screenshots";
    if (!fs.existsSync(auditDir)) {
        fs.mkdirSync(auditDir, { recursive: true });
    }

    let browser;
    try {
        console.log('🚀 正在连接 Omni-Chrome (9222)...');
        browser = await chromium.connectOverCDP('http://localhost:9222');
        const context = browser.contexts()[0];
        let page = context.pages().find(p => p.url().includes('feishu.cn/share/base/query'));

        if (!page) {
            console.log('⚠️ 未找到查重页面，尝试在前台 Tab 中查找...');
            // 如果没找到，可能需要刷新或确保 URL 正确
            return;
        }

        const auditResults = [];

        console.log(`🎬 开始测试查重功能，共计 ${accountIds.length} 个账号...`);

        for (let i = 0; i < accountIds.length; i++) {
            const id = accountIds[i];
            console.log(`[${i + 1}/${accountIds.length}] 正在查重: ${id}...`);

            // 1. 输入数据
            const input = page.locator('input[placeholder*="Enter here"]');
            await input.fill(id);

            // 2. 点击搜索
            const searchBtn = page.locator('button:has-text("Search")');
            await searchBtn.click();

            // 3. 等待响应
            await page.waitForTimeout(3000); // 增加一点等待时间确保渲染完成

            // 4. 结果判定
            const checkResult = await page.evaluate(() => {
                const bodyText = document.body.innerText;
                const noData = bodyText.match(/No data/i) || bodyText.match(/暂无数据/i);

                // 查找列表容器
                const items = document.querySelectorAll('.bitable-grid-row, [class*="item"], [class*="record"]');
                const hasDetails = items.length > 0;

                return {
                    isDuplicate: !noData && hasDetails,
                    itemCount: items.length,
                    displayText: bodyText.substring(0, 500) // 采样部分文本用于调试
                };
            });

            const status = checkResult.isDuplicate ? '❌ 重复 (Duplicate)' : '✅ 可用 (Available)';
            console.log(`   结果: ${status} (找到 ${checkResult.itemCount} 条记录)`);

            auditResults.push({ id, status, details: checkResult });

            // 5. 截图存档
            const filename = `test_audit_${i + 1}_${id.replace(/[^a-z0-9]/gi, '_')}.png`;
            const screenshotPath = path.join(auditDir, filename);
            await page.screenshot({ path: screenshotPath });
            console.log(`   📸 截图已保存: ${filename}`);

            // 为了下次查询，清除输入 (可选，fill 会覆盖)
        }

        console.log('\n--- 测试结果汇总 ---');
        console.table(auditResults.map(r => ({ "账号ID": r.id, "状态": r.status })));

    } catch (error) {
        console.error('\n❌ 运行报错:', error.message);
    } finally {
        if (browser) await browser.disconnect();
    }
}

main();
