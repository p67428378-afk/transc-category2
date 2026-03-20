from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi import Depends
import pytest
import os
import shutil

from app.main import app
from app.database.database import Base, get_db
from app.etl.pipeline import run_etl_pipeline

# Setup for in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the get_db dependency for testing
@pytest.fixture(name="db_session")
def db_session_fixture():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(name="client")
def client_fixture(db_session: Session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_read_root(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Automated Transaction Categorization System API"}

def test_upload_transactions_csv(client: TestClient, mocker):
    mock_run_etl = mocker.patch("app.routers.transactions.run_etl_pipeline")
    
    csv_content = "col1,col2\nval1,val2"
    files = {"file": ("transactions.csv", csv_content, "text/csv")}
    response = client.post("/api/transactions/upload", files=files)
    
    assert response.status_code == 200
    assert response.json()["message"] == "Transaction upload initiated successfully"
    mock_run_etl.assert_called_once()

def test_upload_transactions_invalid_file_type(client: TestClient):
    files = {"file": ("transactions.txt", "some content", "text/plain")}
    response = client.post("/api/transactions/upload", files=files)
    
    assert response.status_code == 400
    assert response.json()["detail"] == "Only CSV files are allowed"
