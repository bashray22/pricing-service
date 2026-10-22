import os
import json
import time
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

app = FastAPI(title="خدمة التسعير", version="1.0")

# ───── المفتاح · من البيئة · مش من الكود ─────
SERVICE_KEY = os.environ.get("PRICING_API_KEY", "")

# ───── التسجيل والمقاييس ─────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pricing")

بدأت_الخدمة = time.time()

عدادات = {
    "requests_total": 0,
    "errors_total": 0,
    "latency_ms_sum": 0.0,
    "latency_ms_max": 0.0,
}

حسب_المسار = {}

TOKENS_PER_QUOTE = 1500
USD_PER_1K_TOKENS = 0.002
استهلاك = {"tokens": 0}


@app.middleware("http")
async def قيس_كل_طلب(request: Request, call_next):
    """يقيس زمن كل طلب ويسجّله ويعدّه."""
    بلّش = time.perf_counter()
    رد = await call_next(request)
    مدة = (time.perf_counter() - بلّش) * 1000

    عدادات["requests_total"] += 1

    مسار = request.url.path
    حسب_المسار[مسار] = حسب_المسار.get(مسار, 0) + 1

    if مسار == "/quote" and رد.status_code == 200:
    استهلاك["tokens"] += TOKENS_PER_QUOTE

    عدادات["latency_ms_sum"] += مدة
    if مدة > عدادات["latency_ms_max"]:
        عدادات["latency_ms_max"] = مدة

    if رد.status_code >= 400:
        عدادات["errors_total"] += 1

    مستوى = logging.WARNING if رد.status_code >= 400 else logging.INFO

    log.log(
        مستوى,
        "path=%s | status=%s | ms=%.1f",
        request.url.path,
        رد.status_code,
        مدة,
    )
    return رد


@app.get("/metrics")
def metrics():
    """أرقام الخدمة للمراقبة."""
    ن = عدادات["requests_total"]

    return {
        "uptime_seconds": round(time.time() - بدأت_الخدمة, 1),
        "requests_total": ن,
        "errors_total": عدادات["errors_total"],
        "latency_ms_avg": (
            round(عدادات["latency_ms_sum"] / ن, 2) if ن else 0
        ),
        "latency_ms_max": round(عدادات["latency_ms_max"], 2),
        "by_path": dict(حسب_المسار),
        "estimated_tokens": استهلاك["tokens"],
        "estimated_cost_usd": round(
         استهلاك["tokens"] / 1000 * USD_PER_1K_TOKENS, 6
),
    }


# ───── البيانات ─────
CATALOG = {
    "A-100": ("سعر الكتالوج 120 دينار", 120),
    "A-200": ("سعر الكتالوج 80 دينار", 80),
    "A-300": ("سعر الكتالوج 45 دينار", 45),
}
PROMOS = {
    "A-100": ("سعر العرض 95 دينار", 95),
}

# ───── الحالة · بملف ─────
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
    """ترجع السعر النهائي الأرخص مع تنبيه عن البدائل."""
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
<p>النسخة ٢ · وهاي على الإنترنت — مش على جهازك</p>
<a href="/quote?code=A-100">/quote?code=A-100</a>
<a href="/health">/health</a>
<a href="/stats">/stats</a>
<a href="/docs">/docs</a>
</div></body></html>"""


@app.get("/health")
def health(response: Response):
    فحوصات = {
        "catalog_loaded": len(CATALOG) > 0,
        "promos_loaded": len(PROMOS) > 0,
        "can_price": bool(سعّر("A-100")),
    }
    سليمة = all(فحوصات.values())

    if not سليمة:
        response.status_code = 503

    return {
        "status": "ok" if سليمة else "unhealthy",
        "checks": فحوصات,
        "key_loaded": bool(SERVICE_KEY),
        "requests": اقرا_العداد(),
    }

@app.get("/quote")
def quote(code: str):
    """ترجع السعر النهائي لمنتج حسب كوده."""
    رد = سعّر(code)

    if not رد:
        raise HTTPException(
            status_code=404,
            detail=f"ما لقيت سعر للكود {code}.",
        )

    زيّد_العداد()
    return {"code": code, "answer": رد}


@app.get("/stats")
def stats():
    """عدد طلبات التسعير المسجلة."""
    return {"count": اقرا_العداد()}
