// Render the 3DsetuPia panel headlessly with a mocked `orca` bridge and save screenshots.
// Usage: python tools/preview_ui.py docs/img && node tools/preview_ui.js docs/img
// Fails (exit 1) if the page throws a JavaScript error.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const root = path.join(__dirname, '..');
const out = process.argv[2] || path.join(root, 'docs', 'img');
const data = JSON.parse(fs.readFileSync(path.join(out, '_preview_payloads.json'), 'utf8'));
const html = fs.readFileSync(path.join(root, 'src', 'ayarci', 'ui.html'), 'utf8');
const MOCK = `window.__sent=[];window.orca={_h:[],postMessage:function(m){window.__sent.push(m);var s=this;
 if(m.command==='init')setTimeout(function(){s._h.forEach(function(h){h(window.__INIT)})},10);
 if(m.command==='analyze')setTimeout(function(){s._h.forEach(function(h){h(window.__PROP)})},10);},
 onMessage:function(cb){this._h.push(cb)},close:function(){}};`;
const THEMES = {
  light: '--orca-bg:#ffffff;--orca-fg:#262e30;--orca-muted:#6b6b6b;--orca-border:#dbdbdb;--orca-accent:#009688',
  dark: '--orca-bg:#2d2d31;--orca-fg:#e8e8e8;--orca-muted:#9a9aa0;--orca-border:#4a4a50;--orca-accent:#00a693',
};

(async () => {
  const errors = [];
  const browser = await chromium.launch();
  for (const lang of ['tr', 'en']) {
    for (const scheme of ['light', 'dark']) {
      const page = await browser.newPage({ viewport: { width: 460, height: 1700 }, deviceScaleFactor: 2 });
      page.on('pageerror', e => errors.push(String(e)));
      page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
      const mock = MOCK + `window.__INIT=${JSON.stringify(data[lang].init)};window.__PROP=${JSON.stringify(data[lang].prop)};`;
      // OrcaSlicer injects its bridge and theme variables at document start; do the same here.
      await page.setContent(html.replace('<head>', `<head><script>${mock}</script><style>:root{${THEMES[scheme]}}</style>`));
      await page.waitForTimeout(150);
      if (scheme === 'light') {
        await page.click('#tabS');
        await page.waitForTimeout(80);
        await page.screenshot({ path: path.join(out, `ayarlar_${lang}.png`), fullPage: true });
        // switch provider to a local one: key box must grey out, address box must be editable
        await page.selectOption('#provider', 'ollama');
        const keyDisabled = await page.$eval('#key', e => e.disabled);
        const urlDisabled = await page.$eval('#url', e => e.disabled);
        if (!keyDisabled || urlDisabled) errors.push('ollama: key should be disabled and url editable');
        await page.selectOption('#provider', 'openai');
        const urlFixed = await page.$eval('#url', e => e.disabled);
        const keyOn = await page.$eval('#key', e => !e.disabled);
        if (!urlFixed || !keyOn) errors.push('openai: url should be fixed and key enabled');
        await page.selectOption('#provider', 'anthropic');
        await page.click('#tabA');
      }
      await page.click('#go');
      await page.waitForTimeout(250);
      await page.screenshot({ path: path.join(out, `asistan_${lang}_${scheme}.png`), fullPage: true });
      // the apply button must send the selected ids
      await page.click('#apply');
      const sent = await page.evaluate(() => window.__sent.filter(m => m.command === 'apply'));
      if (!sent.length || !sent[0].ids.length) errors.push('apply did not send ids');
      await page.close();
    }
  }
  await browser.close();
  if (errors.length) { console.error('UI errors:', errors); process.exit(1); }
  console.log('ok ->', out);
})();
