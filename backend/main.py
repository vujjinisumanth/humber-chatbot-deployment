import os
from contextlib import asynccontextmanager
from typing import Optional

import pandas as pd
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from matcher import load_fulltime, apply_filters, rank_programs, FULLTIME_XLSX
from scheduler import scheduler, scrape_job, MONTHLY_DAY, MONTHLY_HOUR, MONTHLY_MINUTE

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
INDEX_FILE = os.path.join(FRONTEND_DIR, "index.html")

df = pd.DataFrame()


def load_dataset():
    global df
    try:
        df = load_fulltime(FULLTIME_XLSX)
        print(f"[DATA] Loaded {len(df)} programs from {FULLTIME_XLSX}")
    except FileNotFoundError:
        df = pd.DataFrame()
        print(f"[WARN] Dataset file not found: {FULLTIME_XLSX}")
    except Exception as e:
        df = pd.DataFrame()
        print(f"[WARN] Failed to load dataset: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dataset()

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

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def serve_frontend():
    return FileResponse(INDEX_FILE)


@app.get("/health")
def health():
    return {
        "status": "running",
        "programs_loaded": len(df) if not df.empty else 0,
        "dataset_loaded": not df.empty,
        "dataset_path": FULLTIME_XLSX,
        "scheduler_running": scheduler.running,
        "monthly_schedule": {
            "day": MONTHLY_DAY,
            "hour": MONTHLY_HOUR,
            "minute": MONTHLY_MINUTE
        }
    }


@app.get("/filters")
def get_filters():
    if df.empty:
        raise HTTPException(
            status_code=503,
            detail="Dataset not loaded. Make sure Humber_FullTime2.xlsx exists in backend/output/."
        )

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
    if df.empty:
        raise HTTPException(
            status_code=503,
            detail="Dataset not loaded. Make sure Humber_FullTime2.xlsx exists in backend/output/."
        )

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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)