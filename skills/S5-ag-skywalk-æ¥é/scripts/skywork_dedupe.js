const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');
const { parse } = require('querystring');

/**
 * Skywork 自动查重脚本
 * 功能：接管 Omni-Chrome 并批量执行飞书查重
 */

async function main() {
    const csvPath = process.argv[2];
    if (!csvPath) {
        console.error('❌ 请提供 CSV 文件路径。');
        process.exit(1);
    }

    let browser;
    try {
        console.log('🚀 正在连接 Omni-Chrome (9222)...');
        browser = await chromium.connectOverCDP('http://localhost:9222');
        const context = browser.contexts()[0];
        const page = context.pages().find(p => p.url().includes('feishu.cn/share/base/query'));

        if (!page) {
            console.error('❌ 未找到飞书查重页面，请确保已打开目标 Tab。');
            return;
        }

        const content = fs.readFileSync(csvPath, 'utf8');
        const lines = content.split('\n');
        const header = lines[0];
        const results = [header + ',查重状态,查重时间'];

        console.log(`🎬 开始处理数据，共计 ${lines.length - 1} 行...`);

        // 处理逻辑 (跳过标题行)
        for (let i = 1; i < lines.length; i++) {
            if (!lines[i].trim()) continue;

            const columns = lines[i].split(',');
            const bloggerId = columns[3]; // D列 (索引3)

            process.stdout.write(`进度: [${i}/${lines.length - 1}] 正在查重: ${bloggerId}... `);

            // 1. 输入数据
            const input = page.locator('input[placeholder*="Enter here"]');
            await input.fill(bloggerId);

            // 2. 点击搜索
            const searchBtn = page.locator('button:has-text("Search")');
            await searchBtn.click();

        // 3. 等待响应 (飞书推荐 2-3s)
            await page.waitForTimeout(2500);

            // 4. 结果判定
            const isDup = await page.evaluate(() => {
                const bodyText = document.body.innerText;
                const noData = bodyText.match(/No data/i) || bodyText.match(/暂无数据/i);
                const items = document.querySelectorAll('[class*="item"], [class*="record"]');
                return !noData && items.length > 5;
            });

            const status = isDup ? '❌ 重复' : '✅ 可用';
            console.log(status);

            results.push(`${lines[i].trim()},${status},${new Date().toLocaleString()}`);

            // 每 10 条保存一次进度并捕获 QC 截图
            if (i % 10 === 0) {
                const screenshotPath = path.join(__dirname, '../audit_screenshots', `qc_check_row_${i}_${bloggerId.replace(/[^a-z0-9]/gi, '_')}.png`);
                await page.screenshot({ path: screenshotPath });

                fs.writeFileSync(csvPath.replace('.csv', '_dedupe_progress.csv'), results.join('\n'));
            }
        }

        const outPath = csvPath.replace('.csv', `_查重完成_${new Date().toISOString().split('T')[0]}.csv`);
        fs.writeFileSync(outPath, results.join('\n'));
        console.log(`\n🎉 任务全量完成！结果已保存至:\n${outPath}`);

    } catch (error) {
        console.error('\n❌ 运行报错:', error.message);
    } finally {
        if (browser) await browser.disconnect();
    }
}

main();
