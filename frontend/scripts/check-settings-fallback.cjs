// Test a built frontend served at SITE_URL, using mocked settings responses only.
// PLAYWRIGHT_MODULE and BROWSER_PATH may point to existing local test tools.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');

(async () => {
    const browser = await chromium.launch({
        headless: true,
        executablePath: process.env.BROWSER_PATH || undefined,
    });
    try {
        const page = await browser.newPage();
        const mutations = [];
        let mode = 'full';
        await page.addInitScript(() => {
            localStorage.setItem('hasSeenStorageNotice', 'true');
            localStorage.setItem('lastVisit', new Date().toDateString());
        });
        await page.route('**/site-settings', async route => {
            if (route.request().method() !== 'GET') {
                mutations.push(route.request().method());
                return route.abort();
            }
            if (mode === 'offline') return route.abort('failed');
            if (mode === 'timeout') return; // Leave the request pending until aborted.
            if (mode === 'unavailable') return route.fulfill({ status: 503, body: 'Unavailable' });
            if (mode === 'malformed') return route.fulfill({ contentType: 'application/json', body: '{' });
            if (mode === 'missing') return route.fulfill({ json: {} });
            if (mode === 'invalid') return route.fulfill({ json: { minimal_mode: 'false' } });
            return route.fulfill({ json: { minimal_mode: mode !== 'full' } });
        });
        const fullLink = page.locator('a[href="/portfolio"]').first();
        const load = () => page.goto(process.env.SITE_URL || 'http://127.0.0.1:18123', { waitUntil: 'domcontentloaded' });
        const refresh = () => page.evaluate(() => window.dispatchEvent(new Event('online')));
        await load();
        await fullLink.waitFor({ state: 'visible' });
        for (const failure of ['unavailable', 'malformed', 'missing', 'invalid', 'offline', 'timeout']) {
            mode = failure;
            await refresh();
            await fullLink.waitFor({ state: 'detached', timeout: 12000 });
            mode = 'full';
            await refresh();
            await fullLink.waitFor({ state: 'visible' });
            console.log(`PASS: ${failure} redacts; explicit backend setting restores full view`);
        }
        mode = 'unavailable';
        await page.addInitScript(() => {
            window.fullViewExposed = false;
            new MutationObserver(() => {
                if (document.querySelector('a[href="/portfolio"]')) window.fullViewExposed = true;
            }).observe(document, { childList: true, subtree: true });
        });
        await load();
        await page.waitForTimeout(1500);
        assert.equal(await fullLink.count(), 0);
        assert.equal(await page.evaluate(() => window.fullViewExposed), false, 'Full view flashed during failed cold load');
        mode = 'full';
        await refresh();
        await fullLink.waitFor({ state: 'visible' });
        await page.evaluate(() => window.dispatchEvent(new Event('offline')));
        await fullLink.waitFor({ state: 'detached' });
        mode = 'redacted';
        await refresh();
        await page.waitForTimeout(250);
        assert.equal(await fullLink.count(), 0);
        assert.deepEqual(mutations, [], 'Fallback must never modify the stored admin setting');
        console.log('PASS: cold-load privacy, offline event, stored redaction, no settings writes');
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
