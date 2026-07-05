import { test, expect } from '@playwright/test';

test.describe('Auth smoke suite', () => {
  test('login page renders and has expected elements', async ({ page }) => {
    await page.goto('/login');
    await expect(page).toHaveTitle(/Autoniix/i);
    await expect(page.getByRole('heading', { name: /sign in|log in|welcome/i })).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
  });

  test('unauthenticated /dashboard redirects to /login', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/);
  });

  test('register page renders with required fields', async ({ page }) => {
    await page.goto('/register');
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
  });

  test('forgot-password page renders', async ({ page }) => {
    await page.goto('/forgot-password');
    await expect(page.getByLabel(/email/i)).toBeVisible();
  });
});

test.describe('Page metadata', () => {
  test('login page has correct page title', async ({ page }) => {
    await page.goto('/login');
    await expect(page).toHaveTitle('Autoniix');
  });

  test('register page is accessible', async ({ page }) => {
    await page.goto('/register');
    const main = page.locator('main, [id="main-content"], form').first();
    await expect(main).toBeVisible();
  });
});
