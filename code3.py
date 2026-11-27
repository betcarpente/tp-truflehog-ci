# CODE 3 TROUVER LA VERSION CORRIGEE
from pathlib import Path

from fastapi import HTTPException

REPORTS_DIR = Path("/var/reports").resolve()

@app.get("/api/reports/download")
def download_report(filename: str):
    file_path = (REPORTS_DIR / filename).resolve()
    try:
        file_path.relative_to(REPORTS_DIR)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")

    with open(file_path, "r") as f:
        return {"content": f.read()}