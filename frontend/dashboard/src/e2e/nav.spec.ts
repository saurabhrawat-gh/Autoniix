import { test, expect } from '@playwright/test';

test.describe('Protected route redirects', () => {
  const protectedRoutes = [
    '/dashboard',
    '/channels',
    '/providers',
    '/jobs',
    '/review',
    '/library',
    '/settings',
    '/progress',
    '/experiments',
  ];

  for (const route of protectedRoutes) {
    test(`unauthenticated ${route} redirects to /login`, async ({ page }) => {
      await page.goto(route);
      await expect(page).toHaveURL(/\/login/);
    });
  }
});

test.describe('Login page interactions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
  });

  test('has correct page title', async ({ page }) => {
    await expect(page).toHaveTitle(/Autoniix/i);
  });

  test('shows email and password fields', async ({ page }) => {
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
  });

  test('submit button is enabled when fields filled', async ({ page }) => {
    await page.getByLabel(/email/i).fill('user@example.com');
    await page.getByLabel(/password/i).fill('secret123');
    await expect(
      page.getByRole('button', { name: /sign in|log in|submit/i }),
    ).toBeEnabled();
  });

  test('shows error feedback on invalid credentials', async ({ page }) => {
    await page.getByLabel(/email/i).fill('bad@example.com');
    await page.getByLabel(/password/i).fill('wrongpass');
    await page.getByRole('button', { name: /sign in|log in|submit/i }).click();
    await expect(
      page.getByRole('alert').or(page.getByText(/invalid|incorrect|error/i)).first(),
    ).toBeVisible({ timeout: 5000 });
  });

  test('has link to register page', async ({ page }) => {
    const registerLink = page.getByRole('link', { name: /register|sign up|create account/i });
    await expect(registerLink).toBeVisible();
  });

  test('has link to forgot-password page', async ({ page }) => {
    const forgotLink = page.getByRole('link', { name: /forgot|reset/i });
    await expect(forgotLink).toBeVisible();
  });
});

test.describe('Register page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/register');
  });

  test('shows required form fields', async ({ page }) => {
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i).first()).toBeVisible();
  });

  test('is accessible — main landmark exists', async ({ page }) => {
    const main = page.locator('main, [id="main-content"], form').first();
    await expect(main).toBeVisible();
  });
});

test.describe('Forgot-password page', () => {
  test('renders email input and submit button', async ({ page }) => {
    await page.goto('/forgot-password');
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(
      page.getByRole('button', { name: /reset|send|submit/i }),
    ).toBeVisible();
  });
});
