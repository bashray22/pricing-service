# ════════════════════════════════════════════════════════════
#  المحاضرة ٢١ · الخدمة اللي رح ننشرها
#
#  ⚠ ما بتعدّلوا هالملف بالعملي — بتنشروه زي ما هو.
#     (إلا بالتاسكات الإضافية · وهناك بنقلّكم وين بالضبط)
#
#  محلياً:  uvicorn app:app --reload
#  بالحاوية: بيشتغل على 0.0.0.0:10000
# ════════════════════════════════════════════════════════════
import os
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

app = FastAPI(title="خدمة التسعير", version="1.0")

# ───── المفتاح · من البيئة · مش من الكود ─────
SERVICE_KEY = os.environ.get("PRICING_API_KEY", "")

# ───── البيانات ─────
CATALOG = {"A-100": ("سعر الكتالوج 120 دينار", 120),
           "A-200": ("سعر الكتالوج 80 دينار",  80),
           "A-300": ("سعر الكتالوج 45 دينار",  45)}
PROMOS  = {"A-100": ("سعر العرض 95 دينار",      95)}

# ───── الحالة · بملف · زي ما صلّحناها بمحاضرة ٢٠ ─────
STATE = Path("state.json")


def اقرا_العداد() -> int:
    try:
        return int(json.loads(STATE.read_text())["count"])
    except Exception:
        return 0


def زيّد_العداد() -> int:
    n = اقرا_العداد() + 1
    try:
        STATE.write_text(json.dumps({"count": n}))
    except Exception:
        pass
    return n


def سعّر(code: str) -> str:
    """بترجّع السعر النهائي — الأرخص · مع تنبيه عن الباقي."""
    نتائج = []
    if code in CATALOG:
        نتائج.append(("catalog",) + CATALOG[code])
    if code in PROMOS:
        نتائج.append(("promo",) + PROMOS[code])
    if not نتائج:
        return ""
    src, txt, price = min(نتائج, key=lambda f: f[2])
    رد = txt
    باقي = [f for f in نتائج if f[0] != src]
    if باقي:
        رد += " · تنبيه: " + " · ".join(t for _, t, _ in باقي)
    return رد


@app.get("/", response_class=HTMLResponse)
def home():
    """صفحة الترحيب."""
    return """<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>خدمة التسعير</title>
<style>
 body{font-family:system-ui,sans-serif;background:#0f1419;color:#e8eaed;
      display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}
 .c{text-align:center;padding:40px}
 h1{font-size:34px;margin:0 0 10px}
 p{color:#9aa0a6;margin:0 0 26px}
 a{display:inline-block;margin:6px;padding:10px 18px;border-radius:8px;
   background:#1f2937;color:#e8eaed;text-decoration:none;font-family:monospace}
 a:hover{background:#2d3748}
</style></head><body><div class="c">
<h1>خدمة التسعير شغّالة ✓</h1>
# <p>وهاي على الإنترنت — مش على جهازك</p>
<p>النسخة ٢ · وهاي على الإنترنت — مش على جهازك</p>
<a href="/quote?code=A-100">/quote?code=A-100</a>
<a href="/health">/health</a>
<a href="/stats">/stats</a>
<a href="/docs">/docs</a>
</div></body></html>"""


@app.get("/health")
def health():
    """حالة الخدمة · وهل المفتاح محمّل."""
    return {"status": "ok",
            "key_loaded": bool(SERVICE_KEY),
            "requests": اقرا_العداد()}


@app.get("/quote")
def quote(code: str):
    """بترجّع السعر النهائي لمنتج حسب كوده."""
    رد = سعّر(code)
    if not رد:
        raise HTTPException(status_code=404,
                            detail=f"ما لقيت سعر للكود {code}.")
    زيّد_العداد()
    return {"code": code, "answer": رد}


@app.get("/stats")
def stats():
    """كم طلب تسعير وصل من آخر إعادة تشغيل."""
    return {"count": اقرا_العداد()}
