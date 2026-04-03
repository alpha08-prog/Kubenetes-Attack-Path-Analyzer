import { test, expect, Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const SCREENSHOT_DIR = 'playwright-report/screenshots';

// Ensure screenshot directory exists
function ensureScreenshotDir() {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }
}

// Detect horizontal overflow anywhere in the document
async function detectHorizontalOverflow(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const offenders: string[] = [];
    const docWidth = document.documentElement.clientWidth;
    document.querySelectorAll('*').forEach((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.right > docWidth + 2) {
        const tag = el.tagName;
        const cls = (el.className?.toString() || '').slice(0, 60);
        offenders.push(`${tag}[${cls}] right=${rect.right.toFixed(0)} docWidth=${docWidth}`);
      }
    });
    return offenders.slice(0, 20);
  });
}

// Check if the document itself overflows horizontally
async function hasDocumentOverflow(page: Page): Promise<boolean> {
  return page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2
  );
}

const ROUTES = [
  { path: '/', name: 'dashboard' },
  { path: '/demo', name: 'demo-mode' },
  { path: '/nonexistent', name: 'not-found' },
];

test.beforeEach(() => {
  ensureScreenshotDir();
});

// ─── Route exploration ──────────────────────────────────────────────────────

test.describe('Route exploration', () => {
  for (const route of ROUTES) {
    test(`[${route.name}] renders and captures screenshot`, async ({ page }, testInfo) => {
      const consoleErrors: string[] = [];
      const networkFailures: string[] = [];

      page.on('console', (msg) => {
        if (msg.type() === 'error') consoleErrors.push(msg.text());
      });
      page.on('requestfailed', (req) => {
        networkFailures.push(`${req.method()} ${req.url()} — ${req.failure()?.errorText}`);
      });

      await page.goto(route.path);
      // Wait for DOM to settle; networkidle may timeout if API keeps retrying
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(1000);

      // Full-page screenshot
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `${route.name}-initial.png`),
        fullPage: true,
      });

      // Overflow audit
      const overflowOffenders = await detectHorizontalOverflow(page);
      const hasOverflow = await hasDocumentOverflow(page);

      // Attach findings to report
      await testInfo.attach('horizontal-overflow', {
        body: JSON.stringify({ hasOverflow, offenders: overflowOffenders }, null, 2),
        contentType: 'application/json',
      });
      await testInfo.attach('console-errors', {
        body: JSON.stringify(consoleErrors, null, 2),
        contentType: 'application/json',
      });
      await testInfo.attach('network-failures', {
        body: JSON.stringify(networkFailures, null, 2),
        contentType: 'application/json',
      });

      // Page must render real content
      const bodyText = await page.locator('body').textContent();
      expect(bodyText?.trim().length, 'Page should not be blank').toBeGreaterThan(0);

      // Log findings to console for CI visibility
      if (overflowOffenders.length > 0) {
        console.warn(`[${route.name}] Overflow detected:`, overflowOffenders);
      }
      if (consoleErrors.length > 0) {
        console.warn(`[${route.name}] Console errors:`, consoleErrors);
      }
    });
  }
});

// ─── Dashboard interactions ─────────────────────────────────────────────────

test.describe('Dashboard interactions', () => {
  test('Header — Reload Graph button is visible and clickable', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const reloadBtn = page.getByRole('button', { name: /reload graph/i });
    await expect(reloadBtn).toBeVisible();
    await reloadBtn.click();
    // Button goes into loading state (spinner); just verify it didn't crash
    await page.waitForTimeout(500);
  });

  test('Header — Run Demo button navigates to /demo', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    await page.getByRole('button', { name: /run demo/i }).click();
    await expect(page).toHaveURL('/demo');
  });

  test('Overlay toggles — all four modes activate without crash', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    for (const label of ['Default', 'Attack Path', 'Blast Radius', 'Cycles']) {
      const btn = page.getByRole('button', { name: label }).first();
      await expect(btn).toBeVisible();
      await btn.click();
      await page.waitForTimeout(200);
    }
  });

  test('Analysis tabs — all four panels are navigable', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    for (const label of ['Attack Path', 'Blast Radius', 'Cycles & Critical', 'Simulation']) {
      const tab = page.getByRole('button', { name: label }).last();
      await expect(tab).toBeVisible();
      await tab.click();
      await page.waitForTimeout(200);
    }
  });

  test('NarratorPanel — expand/collapse toggle works', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const narratorBtn = page.getByRole('button', { name: /generate ai security report/i });
    if (await narratorBtn.isVisible()) {
      await narratorBtn.click();
      await page.waitForTimeout(500);
      await narratorBtn.click();
    }
  });

  test('Dashboard screenshot at current viewport', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'dashboard-desktop.png'),
      fullPage: false,
    });
  });
});

// ─── DemoMode interactions ───────────────────────────────────────────────────

test.describe('DemoMode interactions', () => {
  test('Controls are present', async ({ page }) => {
    await page.goto('/demo');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByRole('button', { name: /pause|resume/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /restart/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /dashboard/i })).toBeVisible();
  });

  test('Pause/Resume toggle works', async ({ page }) => {
    await page.goto('/demo');
    await page.waitForLoadState('domcontentloaded');

    const pauseBtn = page.getByRole('button', { name: /pause/i }).first();
    if (await pauseBtn.isVisible()) {
      await pauseBtn.click();
      await expect(page.getByRole('button', { name: /resume/i })).toBeVisible();
    }
  });

  test('Back to Dashboard navigates to /', async ({ page }) => {
    await page.goto('/demo');
    await page.waitForLoadState('domcontentloaded');

    await page.getByRole('button', { name: /dashboard/i }).click();
    await expect(page).toHaveURL('/');
  });

  test('DemoMode screenshot at current viewport', async ({ page }) => {
    await page.goto('/demo');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'demo-desktop.png'),
      fullPage: false,
    });
  });
});

// ─── NotFound page ───────────────────────────────────────────────────────────

test.describe('NotFound page', () => {
  test('404 page renders correctly with home link', async ({ page }) => {
    await page.goto('/nonexistent');
    await expect(page.getByText('404')).toBeVisible();
    await expect(page.getByText(/page not found/i)).toBeVisible();

    const homeLink = page.getByRole('link', { name: /return to home|go home|back/i }).first();
    if (await homeLink.isVisible()) {
      await homeLink.click();
      await expect(page).toHaveURL('/');
    }
  });
});
