const { chromium, request } = require(process.cwd() + '/tmp/playwright_live_check/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const base = process.argv[2];
const screenshotDir = path.join(base, 'screenshots');
const rawDir = path.join(base, 'raw');
fs.mkdirSync(screenshotDir, { recursive: true });

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function htmlPage(title, subtitle, payload) {
  return `<!doctype html>
<html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; background: #0c1117; color: #e6edf3; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
  .bar { position: sticky; top: 0; background: #161b22; border-bottom: 1px solid #30363d; padding: 18px 22px; }
  h1 { font-family: Arial, sans-serif; margin: 0 0 6px; font-size: 24px; letter-spacing: 0; }
  p { margin: 0; color: #9da7b3; font-family: Arial, sans-serif; font-size: 14px; }
  pre { white-space: pre-wrap; word-break: break-word; font-size: 14px; line-height: 1.45; margin: 0; padding: 22px; }
  .ok { color: #7ee787; }
</style></head><body>
  <div class="bar"><h1>${escapeHtml(title)}</h1><p>${escapeHtml(subtitle)}</p></div>
  <pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre>
</body></html>`;
}

async function shotPage(page, url, file, opts = {}) {
  await page.goto(url, { waitUntil: opts.waitUntil || 'domcontentloaded', timeout: opts.timeout || 90000 });
  if (opts.waitFor) await page.waitForTimeout(opts.waitFor);
  await page.screenshot({ path: path.join(screenshotDir, file), fullPage: opts.fullPage ?? true });
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const captures = [];
  try {
    await shotPage(page, 'http://127.0.0.1:3000', 'frontend_home_live.png', { waitUntil: 'networkidle', timeout: 120000, waitFor: 1500, fullPage: true });
    captures.push({ name: 'frontend_home_live', url: 'http://127.0.0.1:3000', file: path.join(screenshotDir, 'frontend_home_live.png') });
  } catch (err) {
    captures.push({ name: 'frontend_home_live', url: 'http://127.0.0.1:3000', error: String(err) });
  }

  for (const [name, url] of [
    ['sbert_health_browser', 'http://127.0.0.1:8002/health'],
    ['sbert_ready_browser', 'http://127.0.0.1:8002/ready'],
    ['ncf_health_browser', 'http://127.0.0.1:8003/health'],
    ['dqn_health_browser', 'http://127.0.0.1:8004/health'],
  ]) {
    try {
      await shotPage(page, url, `${name}.png`, { waitUntil: 'domcontentloaded', timeout: 30000, fullPage: true });
      captures.push({ name, url, file: path.join(screenshotDir, `${name}.png`) });
    } catch (err) {
      captures.push({ name, url, error: String(err) });
    }
  }

  const api = await request.newContext();
  const postScreens = [
    { name: 'sbert_semantic_match_post', url: 'http://127.0.0.1:8002/match/semantic', file: 'sbert_semantic_match.json' },
    { name: 'ncf_recommend_post', url: 'http://127.0.0.1:8003/recommend/ncf', file: 'ncf_recommend.json' },
    { name: 'dqn_rerank_post', url: 'http://127.0.0.1:8004/rerank', file: 'dqn_rerank.json' },
  ];
  for (const item of postScreens) {
    try {
      const payload = JSON.parse(fs.readFileSync(path.join(rawDir, item.file), 'utf8'));
      await page.setContent(htmlPage(item.name, `Captured from ${item.url} at ${new Date().toISOString()}`, payload), { waitUntil: 'domcontentloaded' });
      await page.screenshot({ path: path.join(screenshotDir, `${item.name}.png`), fullPage: true });
      captures.push({ name: item.name, url: item.url, file: path.join(screenshotDir, `${item.name}.png`) });
    } catch (err) {
      captures.push({ name: item.name, url: item.url, error: String(err) });
    }
  }
  await api.dispose();
  await browser.close();
  fs.writeFileSync(path.join(rawDir, 'playwright_screenshot_summary.json'), JSON.stringify({ generated_at: new Date().toISOString(), captures }, null, 2));
}
main().catch((err) => { console.error(err); process.exit(1); });
