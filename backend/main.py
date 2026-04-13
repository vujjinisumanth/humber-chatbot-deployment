import os
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .matcher import load_fulltime, apply_filters, rank_programs, FULLTIME_XLSX
from .scheduler import scheduler, scrape_job, MONTHLY_DAY, MONTHLY_HOUR, MONTHLY_MINUTE

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
INDEX_FILE = os.path.join(FRONTEND_DIR, "index.html")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not scheduler.running:
        scheduler.add_job(
            scrape_job,
            trigger="cron",
            day=MONTHLY_DAY,
            hour=MONTHLY_HOUR,
            minute=MONTHLY_MINUTE,
            id="monthly_humber_scrape",
            replace_existing=True,
            max_instances=1,
        )
        scheduler.start()
        print(
            f"[SCHEDULER] Monthly scrape scheduled for day {MONTHLY_DAY} "
            f"at {MONTHLY_HOUR:02d}:{MONTHLY_MINUTE:02d}"
        )

    yield

    if scheduler.running:
        scheduler.shutdown()


app = FastAPI(
    title="InnovAI - Humber Program Matcher",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

df = load_fulltime(FULLTIME_XLSX)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def serve_frontend():
    return FileResponse(INDEX_FILE)


@app.get("/health")
def health():
    return {
        "status": "running",
        "programs_loaded": len(df),
        "scheduler_running": scheduler.running,
        "monthly_schedule": {
            "day": MONTHLY_DAY,
            "hour": MONTHLY_HOUR,
            "minute": MONTHLY_MINUTE
        }
    }


@app.get("/filters")
def get_filters():
    cred_options = sorted([x for x in df["CREDENTIALS"].unique().tolist() if x])
    return {"credentials": cred_options}


@app.post("/match")
async def match_programs(
    jd_text: str = Form(""),
    file: Optional[UploadFile] = File(None),
    top_k: int = Form(10),
    cred_selected: str = Form(""),
    pgwp_choice: str = Form("All"),
    start_choice: str = Form("All"),
    length_selected: str = Form(""),
    wil_choice: str = Form("All")
):
    if file:
        content = await file.read()
        jd_text = content.decode("utf-8", errors="ignore")

    cred_list = [x.strip() for x in cred_selected.split(",") if x.strip()]
    length_list = [x.strip() for x in length_selected.split(",") if x.strip()]

    filtered = apply_filters(
        df,
        cred_list,
        pgwp_choice,
        start_choice,
        length_list,
        wil_choice
    )

    results = rank_programs(filtered, jd_text, top_k)

    return {
        "results": results,
        "programs_searched": len(filtered),
        "top_k": top_k
    }


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)