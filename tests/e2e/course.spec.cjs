const { test: base, expect } = require('@playwright/test');
const fs = require('node:fs/promises');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

// Fail on unexpected network dependencies and real browser exceptions.
const test = base.extend({
  page: async ({ page }, use) => {
    const errors = [];
    const external = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    await page.route('**/*', route => {
      const url = new URL(route.request().url());
      if (['file:', 'data:', 'blob:'].includes(url.protocol) ||
          (url.protocol === 'http:' && url.hostname === '127.0.0.1' && url.port === '4173')) return route.continue();
      external.push(url.href);
      return route.abort();
    });
    await use(page);
    expect(external, 'The generated course must not request remote resources').toEqual([]);
    expect(errors, 'The browser must not report console errors or uncaught exceptions').toEqual([]);
  }
});

function courseURL(testInfo, suffix = 'index.html') {
  return testInfo.project.metadata.transport === 'file'
    ? pathToFileURL(path.resolve('.e2e', 'site', suffix)).href
    : `http://127.0.0.1:4173/${suffix}`;
}

async function openSidebar(page) {
  if (await page.locator('#menu-toggle').isVisible() &&
      await page.locator('#menu-toggle').getAttribute('aria-expanded') !== 'true') {
    await page.locator('#menu-toggle').click();
  }
}

async function sidebarClick(page, selector) {
  await openSidebar(page);
  await page.locator(selector).click();
}

async function finishCurrentLesson(page) {
  await page.getByRole('button', { name: '03 当日测验', exact: true }).click();
  await page.getByRole('radio', { name: '0.5米', exact: true }).check();
  await page.getByRole('button', { name: '提交答案', exact: true }).click();
  await page.getByRole('button', { name: '下一题 →', exact: true }).click();
  await page.getByRole('radio', { name: '0.25米', exact: true }).check();
  await page.getByRole('button', { name: '提交答案', exact: true }).click();
  await expect(page.locator('.completion')).toBeVisible();
}

async function expectNoPageOverflow(page) {
  const size = await page.evaluate(() => ({
    page: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth
  }));
  expect(size.page).toBeLessThanOrEqual(size.viewport + 1);
}

test('answer gate, retry, focus, reload and same-day completion stay consistent', async ({ page }, testInfo) => {
  await page.goto(courseURL(testInfo));
  await expect(page.locator('#stat-completed')).toHaveText('0 / 2');
  await expect(page.locator('#storage-warning')).toBeHidden();
  await expectNoPageOverflow(page);
  await page.locator('#continue-learning').click();
  const quizTab = page.getByRole('button', { name: '03 当日测验', exact: true });
  await quizTab.click();
  await expect(quizTab).toBeFocused();
  await expect(page.getByRole('button', { name: '提交答案', exact: true })).toBeDisabled();
  await page.getByRole('radio', { name: '500米', exact: true }).check();
  await page.getByRole('button', { name: '提交答案', exact: true }).click();
  await expect(page.locator('.feedback.incorrect')).toBeVisible();
  await expect(page.locator('.completion')).toHaveCount(0);
  await page.getByRole('button', { name: '再试一次', exact: true }).click();
  await expect(page.locator('#answer-option-0')).toBeFocused();
  await page.getByRole('radio', { name: '0.5米', exact: true }).check();
  await page.getByRole('button', { name: '提交答案', exact: true }).click();
  await page.getByRole('button', { name: '下一题 →', exact: true }).click();
  await expect(page.locator('#quiz-question-heading')).toBeFocused();
  await page.getByRole('radio', { name: '0.25米', exact: true }).check();
  await page.getByRole('button', { name: '提交答案', exact: true }).click();
  await expect(page.locator('.completion')).toBeVisible();
  await page.reload();
  await expect(page.locator('.completion')).toBeVisible();
  await sidebarClick(page, '#wrong-book');
  await expect(page.getByText('已订正 · 历史保留', { exact: true })).toBeVisible();
  await sidebarClick(page, '#dashboard-link');
  await expect(page.locator('#stat-completed')).toHaveText('1 / 2');
  await expect(page.locator('#day-completed-count')).toHaveText('1');
  await expect(page.locator('#day-question-count')).toHaveText('2');
  await expect(page.locator('#day-planned-minutes')).toHaveText('10');
  await page.locator('#continue-learning').click();
  await finishCurrentLesson(page);
  await sidebarClick(page, '#dashboard-link');
  await expect(page.locator('#stat-completed')).toHaveText('2 / 2');
  await expect(page.locator('#day-completed-count')).toHaveText('2');
  await expect(page.locator('#day-question-count')).toHaveText('4');
  await expect(page.locator('#day-planned-minutes')).toHaveText('20');
  await expectNoPageOverflow(page);
});

test('real JSON download restores answers and notes in a fresh browser context', async ({ page, browser }, testInfo) => {
  const url = courseURL(testInfo);
  await page.goto(url);
  await page.locator('#continue-learning').click();
  await page.getByRole('button', { name: '02 练习与笔记', exact: true }).click();
  await page.locator('#lesson-notes').fill('备份测试：250毫米 = 0.25米。');
  await finishCurrentLesson(page);
  await openSidebar(page);
  const downloaded = page.waitForEvent('download');
  await page.locator('#export-progress').click();
  const download = await downloaded;
  const backup = testInfo.outputPath('progress.json');
  await download.saveAs(backup);
  const payload = JSON.parse(await fs.readFile(backup, 'utf8'));
  expect(payload.course_id).toBe('ktp-browser-regression');
  expect(Object.keys(payload.answers)).toHaveLength(2);
  expect(payload.notes['l:day-1'].text).toContain('250毫米');
  const fresh = await browser.newContext({ viewport: page.viewportSize(), reducedMotion: 'reduce' });
  try {
    const restored = await fresh.newPage();
    await restored.goto(url);
    await expect(restored.locator('#stat-completed')).toHaveText('0 / 2');
    await restored.locator('#import-file').setInputFiles(backup);
    await expect(restored.locator('#notice')).toContainText('导入完成');
    await expect(restored.locator('#stat-completed')).toHaveText('1 / 2');
    await expect(restored.locator('#day-question-count')).toHaveText('2');
    await restored.locator('#import-file').setInputFiles(backup);
    await expect(restored.locator('#day-question-count')).toHaveText('2');
    await openSidebar(restored);
    await restored.locator('.lesson-link').first().click();
    await restored.getByRole('button', { name: '02 练习与笔记', exact: true }).click();
    await expect(restored.locator('#lesson-notes')).toHaveValue('备份测试：250毫米 = 0.25米。');
    await restored.reload();
    await expect(restored.locator('#lesson-notes')).toHaveValue('备份测试：250毫米 = 0.25米。');
  } finally {
    await fresh.close();
  }
});

test('STEM MathML and embedded SVG render at this viewport and in print mode', async ({ page }, testInfo) => {
  await page.goto(courseURL(testInfo, 'stem/index.html') + '#day-1');
  await expect(page.locator('math').first()).toBeVisible();
  await expect(page.locator('.formula-warning')).toHaveCount(0);
  const image = page.locator('.diagram-image').first();
  await expect(image).toBeVisible();
  await expect.poll(() => image.evaluate(element => element.complete && element.naturalWidth > 0)).toBe(true);
  await expectNoPageOverflow(page);
  await page.emulateMedia({ media: 'print' });
  await expect(page.locator('math').first()).toBeVisible();
  await expect(image).toBeVisible();
});


test('long goals and lesson titles remain readable across narrow layout breakpoints', async ({ page }, testInfo) => {
  await page.goto(courseURL(testInfo, 'layout/index.html'));
  const details = page.locator('.hero-goal');
  await expect(details.locator('p')).toBeHidden();
  await details.locator('summary').click();
  await expect(details.locator('p')).toContainText('完整目标末尾保留核查标记。');
  await expect(details.locator('p')).toBeVisible();
  await details.locator('summary').click();
  await expect(page.locator('.progress-fill')).toHaveCSS('width', '0px');
  for (const width of [390, 580, 600, 768, 800, 801, 1024, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await expectNoPageOverflow(page);
    const columns = await page.locator('.dashboard-stats').evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length);
    expect(columns).toBe(width < 1000 ? 2 : 4);
    await openSidebar(page);
    const title = page.locator('.lesson-title').first();
    const size = await title.boundingBox();
    expect(size.width).toBeGreaterThan(100);
    await expect(page.locator('.lesson-link').first()).toHaveAttribute('aria-label', /从长度单位换算逐步理解数量关系/);
    if (width === 600 || width === 1440) await page.screenshot({ path: testInfo.outputPath(`long-layout-${width}.png`), fullPage: true });
  }
  await page.locator('#continue-learning').click();
  await expect(page.locator('.activity').first()).toContainText('学习');
  await expect(page.locator('.activity').first()).not.toContainText('learn');
});
