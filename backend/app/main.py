from fastapi import FastAPI, Depends
from .database.database import get_db
from .routers import transactions
# Removed: from .etl.pipeline import create_db_and_tables # No longer called directly by app startup

app = FastAPI(
    title="Automated Transaction Categorization System API",
    description="API for uploading, categorizing, and reporting bank transactions.",
    version="1.0.0",
)

# Removed: @app.on_event("startup")
# Removed: def on_startup():
# Removed:    create_db_and_tables() # This was causing the issue

app.include_router(transactions.router, prefix="/api")

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Automated Transaction Categorization System API"}
