"""
Composite WhatsApp mock screenshot onto phone screen in jakub photo,
then crop and save as static/hero.jpg
"""
import subprocess
import sys
import os
import numpy as np
from PIL import Image, ImageFilter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # mocks/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_PHOTO = r"C:\Users\ivana\Downloads\jakub-zerdzicki-jSQCLQA99Og-unsplash.jpg"
WA_HTML = os.path.join(BASE, "whatsapp_mock.html")
WA_SCREENSHOT = os.path.join(SCRIPT_DIR, "wa_screenshot.png")
OUTPUT_HERO = os.path.join(BASE, "..", "static", "hero.jpg")
OUTPUT_HERO = os.path.normpath(OUTPUT_HERO)

# ─── Step 1: Screenshot the WhatsApp mock ───────────────────────────────────
print("Step 1: Screenshotting WhatsApp mock...")

wa_script = f"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={{"width": 393, "height": 852}}, device_scale_factor=2)
        await page.goto("file:///{WA_HTML.replace(chr(92), '/')}")
        await page.wait_for_timeout(1000)
        # Capture just the phone div
        phone = page.locator(".phone")
        await phone.screenshot(path=r"{WA_SCREENSHOT}")
        await browser.close()
        print("Screenshot saved:", r"{WA_SCREENSHOT}")

asyncio.run(main())
"""

result = subprocess.run(
    [sys.executable, "-c", wa_script],
    capture_output=True, text=True, timeout=60
)
print("stdout:", result.stdout)
print("stderr:", result.stderr[-800:] if result.stderr else "")

if not os.path.exists(WA_SCREENSHOT):
    # Fallback: screenshot full page
    wa_script2 = f"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={{"width": 480, "height": 920}}, device_scale_factor=2)
        await page.goto("file:///{WA_HTML.replace(chr(92), '/')}")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=r"{WA_SCREENSHOT}", full_page=False)
        await browser.close()
        print("Fallback screenshot saved")

asyncio.run(main())
"""
    result2 = subprocess.run(
        [sys.executable, "-c", wa_script2],
        capture_output=True, text=True, timeout=60
    )
    print("Fallback:", result2.stdout, result2.stderr[-500:])

print("WA screenshot exists:", os.path.exists(WA_SCREENSHOT))

# ─── Step 2: Detect phone screen coordinates in the source photo ─────────────
print("\nStep 2: Detecting phone screen in jakub photo...")

photo = Image.open(SOURCE_PHOTO).convert("RGB")
W, H = photo.size
print(f"Photo size: {W}x{H}")

photo_np = np.array(photo)

# Find pixels that are very bright (white screen area)
# The phone screen is pure white: R>230, G>230, B>230
bright = (photo_np[:,:,0] > 230) & (photo_np[:,:,1] > 230) & (photo_np[:,:,2] > 230)
bright_uint8 = bright.astype(np.uint8) * 255

# Find the largest connected white rectangle
from PIL import Image as PILImage
bright_img = PILImage.fromarray(bright_uint8)

# Get bounding box of all bright pixels (rough estimate)
bright_coords = np.argwhere(bright)  # row, col
if len(bright_coords) > 0:
    rows = bright_coords[:, 0]
    cols = bright_coords[:, 1]
    # Filter to center region (the screen is in the center)
    center_mask = (cols > W*0.3) & (cols < W*0.65) & (rows > H*0.05) & (rows < H*0.95)
    rows_c = rows[center_mask]
    cols_c = cols[center_mask]
    if len(rows_c) > 0:
        r_min, r_max = rows_c.min(), rows_c.max()
        c_min, c_max = cols_c.min(), cols_c.max()
        print(f"Detected bright region: rows {r_min}-{r_max}, cols {c_min}-{c_max}")
        print(f"Screen width: {c_max-c_min}px, height: {r_max-r_min}px")
    else:
        print("No bright region found in center, using defaults")
        r_min, r_max = 150, 1750
        c_min, c_max = 1050, 1630

# Manual fine-tuned coordinates for this specific photo
# (Based on visual inspection of the 3000x2001 jakub photo)
# The phone screen (blank white) corners — slight perspective tilt
# Top-left, Top-right, Bottom-right, Bottom-left
# These are in (x, y) = (col, row) format
SCREEN_TL = (c_min, r_min)
SCREEN_TR = (c_max, r_min)
SCREEN_BR = (c_max, r_max)
SCREEN_BL = (c_min, r_max)

print(f"Screen corners: TL={SCREEN_TL}, TR={SCREEN_TR}, BR={SCREEN_BR}, BL={SCREEN_BL}")

# ─── Step 3: Load WA screenshot and composite ────────────────────────────────
print("\nStep 3: Compositing WA screenshot onto phone...")

if not os.path.exists(WA_SCREENSHOT):
    print("ERROR: No WA screenshot found, skipping composite")
    wa_img = None
else:
    wa_img = Image.open(WA_SCREENSHOT).convert("RGB")
    print(f"WA screenshot size: {wa_img.size}")

if wa_img is not None:
    screen_w = SCREEN_TR[0] - SCREEN_TL[0]
    screen_h = SCREEN_BL[1] - SCREEN_TL[1]
    print(f"Target screen area: {screen_w}x{screen_h}px")

    # Resize WA screenshot to fit the detected screen area
    wa_resized = wa_img.resize((screen_w, screen_h), Image.LANCZOS)

    # Composite: paste WA screenshot over the white screen area
    composite = photo.copy()
    composite.paste(wa_resized, (SCREEN_TL[0], SCREEN_TL[1]))
    print("Composite done")
else:
    composite = photo.copy()
    print("Using original photo (no WA screenshot)")

# ─── Step 4: Crop for hero band ─────────────────────────────────────────────
print("\nStep 4: Cropping for hero band...")

# Target: phone is dominant with greenery visible on sides
# Crop: slightly tighter than full width, centered on the phone
# Hero aspect ratio: roughly 16:6 (very wide) for a hero band
# The phone center is around x=1350 in the 3000px image

# For a standard hero, let's use the full width but crop vertically
# to focus on the phone area while keeping some greenery visible
# Crop: full width, center vertically on the phone
phone_center_y = (SCREEN_TL[1] + SCREEN_BL[1]) // 2
target_h = 1400  # tall enough for a good hero
crop_top = max(0, phone_center_y - target_h // 2)
crop_bot = min(H, crop_top + target_h)
if crop_bot == H:
    crop_top = max(0, H - target_h)

# Keep full width for hero background
hero_crop = composite.crop((0, crop_top, W, crop_bot))
print(f"Cropped: 0,{crop_top} -> {W},{crop_bot} = {hero_crop.size}")

# Resize to 1400x600 hero size (2.33:1 aspect) — wide banner
hero_final = hero_crop.resize((1400, 600), Image.LANCZOS)
print(f"Final hero size: {hero_final.size}")

# ─── Step 5: Save ───────────────────────────────────────────────────────────
print(f"\nStep 5: Saving to {OUTPUT_HERO}...")
hero_final.save(OUTPUT_HERO, "JPEG", quality=90, optimize=True)
size_kb = os.path.getsize(OUTPUT_HERO) // 1024
print(f"Saved: {size_kb} KB")
print("Done!")
