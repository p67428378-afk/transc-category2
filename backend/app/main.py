from fastapi import FastAPI, Depends
from .database.database import get_db
from .routers import transactions
from .etl.pipeline import create_db_and_tables # Import create_db_and_tables

app = FastAPI(
    title="Automated Transaction Categorization System API",
    description="API for uploading, categorizing, and reporting bank transactions.",
    version="1.0.0",
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables() # Call without argument, uses default engine

app.include_router(transactions.router, prefix="/api")

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Automated Transaction Categorization System API"}
