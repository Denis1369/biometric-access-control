import { expect, test } from '@playwright/test'

test.describe('СКУД smoke', () => {
  test('открывает страницу входа', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByRole('heading', { name: 'СКУД' })).toBeVisible()
    await expect(page.getByText('Вход в систему управления доступом')).toBeVisible()
    await expect(page.getByRole('button', { name: /Войти/ })).toBeVisible()
  })

  test('перенаправляет неавторизованного пользователя на вход', async ({ page }) => {
    await page.goto('/')

    await expect(page).toHaveURL(/\/login/)
    await expect(page.locator('input[autocomplete="username"]')).toBeVisible()
  })
})
