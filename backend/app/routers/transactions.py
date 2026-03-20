from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Annotated
import shutil
import os

from ..database.database import get_db
from ..etl.pipeline import run_etl_pipeline

router = APIRouter()

@router.post("/upload")
async def upload_transactions(background_tasks: BackgroundTasks, file: UploadFile = File(...), user_id: int = 1, db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    # Create a temporary file to store the uploaded CSV
    temp_file_path = f"/tmp/{user_id}_{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Simulate asynchronous processing for larger files
    # For now, we'll run it directly, but in a real scenario, this would trigger a background job
    background_tasks.add_task(run_etl_pipeline, temp_file_path, user_id, db)

    return {"message": "Transaction upload initiated successfully", "filename": file.filename, "job_id": "mock_job_id"}
