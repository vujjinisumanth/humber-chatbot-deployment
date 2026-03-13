from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from matcher import load_fulltime, apply_filters, rank_programs
from typing import Optional
import uvicorn

app = FastAPI(title="InnovAI - Humber Program Matcher")

# Allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load dataset once on startup
from matcher import load_fulltime, apply_filters, rank_programs, FULLTIME_XLSX
df = load_fulltime(FULLTIME_XLSX)


# Serve frontend HTML
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

@app.get("/")
def serve_frontend():
    return FileResponse("../frontend/index.html")

@app.get("/health")
def health():
    return {"status": "running", "programs_loaded": len(df)}

@app.get("/filters")
def get_filters():
    cred_options = sorted([x for x in df["CREDENTIALS"].unique().tolist() if x])
    return {"credentials": cred_options}

@app.post("/match")
async def match_programs(
    jd_text:         str  = Form(""),
    file:            Optional[UploadFile] = File(None),
    top_k:           int  = Form(10),
    cred_selected:   str  = Form(""),   # comma-separated
    pgwp_choice:     str  = Form("All"),
    start_choice:    str  = Form("All"),
    length_selected: str  = Form(""),   # comma-separated
    wil_choice:      str  = Form("All")
):
    # If file uploaded, use file text
    if file:
        content = await file.read()
        jd_text = content.decode("utf-8", errors="ignore")

    # Parse comma-separated filters
    cred_list   = [x.strip() for x in cred_selected.split(",") if x.strip()]
    length_list = [x.strip() for x in length_selected.split(",") if x.strip()]

    filtered = apply_filters(df, cred_list, pgwp_choice,
                             start_choice, length_list, wil_choice)
    results  = rank_programs(filtered, jd_text, top_k)

    return {
        "results":           results,
        "programs_searched": len(filtered),
        "top_k":             top_k
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
