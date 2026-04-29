import asyncio
from playwright.async_api import async_playwright

async def debug_task_create():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()

        # 先登录
        await page.goto('http://localhost:3000/login')
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(1)

        # 填写登录表单
        await page.locator('input[placeholder*="账号"]').fill('admin')
        await page.locator('input[type="password"]').fill('123456')

        # 获取验证码
        captcha_text = await page.evaluate('() => document.querySelector(".captcha-img")?.textContent || ""')
        if captcha_text:
            await page.locator('input[placeholder*="验证码"]').fill(captcha_text.strip())

        # 点击登录 - 使用更精确的选择器
        await page.locator('button[type="submit"]').first.click()
        await asyncio.sleep(3)

        print(f'登录后URL: {page.url}')

        # 访问创建任务页面
        await page.goto('http://localhost:3000/home/task/create/100161')
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(5)

        print(f'创建任务页面URL: {page.url}')

        # 检查页面内容
        content = await page.content()
        print(f'页面内容长度: {len(content)}')
        print(f'页面内容前500字符: {content[:500]}')

        # 检查是否有Vue组件渲染
        has_vue = await page.evaluate('() => typeof Vue !== "undefined"')
        print(f'Vue是否加载: {has_vue}')

        # 截图
        await page.screenshot(path='debug_task_create2.png', full_page=True)
        print('截图已保存')

        await browser.close()

asyncio.run(debug_task_create())
