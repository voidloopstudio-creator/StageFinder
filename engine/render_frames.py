import sys, asyncio, os, pathlib
from playwright.async_api import async_playwright
a, b, outdir = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
html = pathlib.Path(__file__).with_name('ad.html').resolve().as_uri()
os.makedirs(outdir, exist_ok=True)
async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path=os.environ.get('CHROMIUM', '/opt/pw-browsers/chromium'), args=['--no-sandbox', '--allow-file-access-from-files'])
        pg = await br.new_page(viewport={'width': 1080, 'height': 1920})
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(html)
        await pg.wait_for_function('window.READY===true', timeout=30000)
        for i in range(a, b):
            await pg.evaluate(f'render({i/30})')
            await pg.screenshot(path=f'{outdir}/{i:04d}.png')
        await br.close()
        if errs:
            print('JS ERRORS', errs[:3]); sys.exit(2)
asyncio.run(main())
