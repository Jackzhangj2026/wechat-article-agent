"""Batch generate images via HTTP API to avoid DB lock conflicts"""
import asyncio, sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')
log_path = r"d:\Users\Administrator\Documents\Obsidian Vault\new Vault\wechat-article-agent\backend\batch_gen_log.txt"

def log(msg):
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

with open(log_path, "w", encoding="utf-8") as f:
    f.write("")

import httpx

API_BASE = "http://127.0.0.1:8001"

async def main():
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Get all articles
        r = await client.get(f"{API_BASE}/api/articles")
        articles = r.json()["articles"]
        log(f"Found {len(articles)} articles")

        total_ok = 0
        total_fail = 0

        for art in articles:
            aid = art["id"]
            title = art["title"][:40]
            log(f"\n=== Article {aid}: {title} ===")

            # Check existing images
            r2 = await client.get(f"{API_BASE}/api/articles/{aid}/images")
            existing = r2.json()["images"]
            done_ids = {(img["role"], img["index"]) for img in existing if img["status"] == "done" and img["file_path"]}

            # Get article detail for image_plan
            r3 = await client.get(f"{API_BASE}/api/articles/{aid}")
            art_detail = r3.json()
            plan = art_detail.get("image_plan", [])

            # Generate all images (API will create/update records, but done ones will be regenerated)
            # Actually, let's generate one by one using regenerate for failed ones, and new for missing
            # For simplicity, call generate_all_images
            log(f"  Triggering generate_all_images ({len(plan)} images)...")
            t0 = time.time()
            try:
                r4 = await client.post(f"{API_BASE}/api/articles/{aid}/generate_all_images", timeout=600.0)
                elapsed = time.time() - t0
                if r4.status_code == 200:
                    results = r4.json()["results"]
                    for res in results:
                        if res["status"] == "done":
                            total_ok += 1
                            log(f"  OK: idx={res['index']} ({elapsed:.0f}s total)")
                        else:
                            total_fail += 1
                            log(f"  FAIL: idx={res['index']} err={res.get('error','')[:100]}")
                else:
                    log(f"  HTTP ERROR {r4.status_code}: {r4.text[:200]}")
                    total_fail += len(plan)
            except Exception as e:
                log(f"  EXCEPTION: {e}")
                total_fail += len(plan)

        log(f"\n=== DONE: {total_ok} success, {total_fail} failed ===")

asyncio.run(main())
