from fastapi import FastAPI
from .routers import transactions
from .database.database import engine, Base
from .etl.pipeline import create_db_and_tables

app = FastAPI()

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])

@app.get("/")
async def root():
    return {"message": "Welcome to the Automated Transaction Categorization System API"}
