import { test, expect, Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const SCREENSHOT_DIR = 'playwright-report/screenshots';

function ensureScreenshotDir() {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }
}

async function hasHorizontalOverflow(page: Page): Promise<boolean> {
  return page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2
  );
}

const VIEWPORTS = [
  { name: 'mobile',  width: 375,  height: 812  },
  { name: 'tablet',  width: 768,  height: 1024 },
  { name: 'desktop', width: 1440, height: 900  },
];

test.beforeEach(() => {
  ensureScreenshotDir();
});

// ─── Dashboard responsive ────────────────────────────────────────────────────

test.describe('Dashboard — responsive layout', () => {
  for (const vp of VIEWPORTS) {
    test(`[${vp.name}] no horizontal overflow at ${vp.width}px`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(600);

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `dashboard-${vp.name}.png`),
        fullPage: false,
      });

      const overflow = await hasHorizontalOverflow(page);
      expect(overflow, `Horizontal overflow at ${vp.name} (${vp.width}px)`).toBe(false);
    });

    test(`[${vp.name}] header is visible and fits within ${vp.width}px`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');

      // Run Demo button is always visible (text never hidden)
      const runDemoBtn = page.getByRole('button', { name: /run demo/i });
      await expect(runDemoBtn).toBeVisible();

      // The top bar must not extend beyond viewport
      const topBar = page.locator('[class*="border-b"]').first();
      const bbox = await topBar.boundingBox();
      if (bbox) {
        expect(bbox.x + bbox.width).toBeLessThanOrEqual(vp.width + 2);
      }
    });

    test(`[${vp.name}] metrics bar is visible`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');

      // Metrics bar is a horizontal flex row with threat score + stat cards
      // Check that stat cards are visible by looking for "Total Nodes" text
      const totalNodesCard = page.getByText('Total Nodes');
      await expect(totalNodesCard).toBeVisible();

      // Also verify the metrics row container itself is visible
      const metricsRow = page.locator('[class*="flex-shrink-0"][class*="flex"][class*="gap-2"][class*="border-b"]').first();
      await expect(metricsRow).toBeVisible();
    });
  }

  test('[mobile] stats flex row does not overflow at 375px', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Stats container is now a flex row, check it fits in viewport
    const statsContainer = page.locator('div').filter({ has: page.locator('div').filter({ hasText: /Total Nodes|Total Edges|Critical Findings/ }).first() }).first();
    const metricsRow = page.locator('[class*="flex-shrink-0"][class*="flex"][class*="gap-2"][class*="border-b"]').first();
    const bbox = await metricsRow.boundingBox();
    if (bbox) {
      expect(bbox.x + bbox.width).toBeLessThanOrEqual(375 + 2);
    }
  });

  test('[mobile] graph and sidebar panels each fill full width when stacked', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(600);

    // Main content container has flex-col on mobile, flex-row on md+
    // Look for the container with 'md:flex-row' in its class to identify main content
    // This will have graph (w-full md:w-[70%]) and sidebar (w-full md:w-[30%]) as children
    const mainContent = page.locator('div[class*="flex-col"][class*="md:flex-row"][class*="min-h-0"]').first();
    const children = mainContent.locator('> div');
    const count = await children.count();

    // On mobile (375px), each panel should be full width (~375px)
    for (let i = 0; i < count; i++) {
      const bbox = await children.nth(i).boundingBox();
      if (bbox && bbox.width > 0) {
        expect(bbox.width).toBeGreaterThan(300);
      }
    }
  });
});

// ─── DemoMode responsive ─────────────────────────────────────────────────────

test.describe('DemoMode — responsive layout', () => {
  for (const vp of VIEWPORTS) {
    test(`[${vp.name}] no horizontal overflow at ${vp.width}px`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/demo');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(600);

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `demo-${vp.name}.png`),
        fullPage: false,
      });

      const overflow = await hasHorizontalOverflow(page);
      expect(overflow, `Horizontal overflow at ${vp.name} (${vp.width}px)`).toBe(false);
    });

    test(`[${vp.name}] top bar fits within ${vp.width}px`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/demo');
      await page.waitForLoadState('domcontentloaded');

      const topBar = page.locator('.border-b.border-border').first();
      const bbox = await topBar.boundingBox();
      if (bbox) {
        expect(bbox.x + bbox.width).toBeLessThanOrEqual(vp.width + 2);
      }
    });

    test(`[${vp.name}] content container is visible and has non-zero size at ${vp.width}px`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/demo');
      await page.waitForLoadState('domcontentloaded');

      const content = page.locator('.max-w-4xl').first();
      await expect(content).toBeVisible();
      const bbox = await content.boundingBox();
      expect(bbox).not.toBeNull();
      // Container must have positive dimensions
      expect(bbox!.width).toBeGreaterThan(0);
      // At desktop widths the container should be centered (has auto margins)
      if (vp.width >= 1024) {
        expect(bbox!.x).toBeGreaterThan(0);
      }
    });
  }
});

// ─── NotFound responsive ──────────────────────────────────────────────────────

test.describe('NotFound — responsive layout', () => {
  for (const vp of VIEWPORTS) {
    test(`[${vp.name}] centered content, no overflow at ${vp.width}px`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/nonexistent');
      await page.waitForLoadState('domcontentloaded');

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `notfound-${vp.name}.png`),
        fullPage: false,
      });

      const overflow = await hasHorizontalOverflow(page);
      expect(overflow, `Horizontal overflow at ${vp.name}`).toBe(false);

      await expect(page.getByText('404')).toBeVisible();
    });
  }
});
