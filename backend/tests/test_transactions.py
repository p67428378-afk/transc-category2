from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi import Depends
import pytest
import os
from io import StringIO

from app.main import app
from app.database.database import Base, get_db
from app.etl.pipeline import run_etl_pipeline
from app.database.models import Transaction, User # Import Transaction and User models

# Setup for in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
# Add check_same_thread=False for SQLite to allow multi-threaded access in tests
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the get_db dependency for testing
@pytest.fixture(name="db_session", scope="module")
def db_session_fixture():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine) # Drop tables after all tests in the module

@pytest.fixture(name="client", scope="module")
def client_fixture():
    # Create a new engine and session for the client to avoid thread issues with SQLite
    test_engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    TestClientSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestClientSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)

# Fixture to create a dummy user for testing ETL pipeline
@pytest.fixture(scope="module")
def dummy_user(db_session: Session):
    user = User(email="test@example.com", hashed_password="hashedpassword")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

def test_read_root(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Automated Transaction Categorization System API"}

def test_upload_transactions_csv_success(client: TestClient, db_session: Session, dummy_user):
    csv_content = "date,description,amount\n2023-01-01,Groceries,50.00\n2023-01-02,Coffee,5.50"
    files = {"file": ("transactions.csv", csv_content, "text/csv")}
    response = client.post(f"/api/transactions/upload?user_id={dummy_user.id}", files=files)
    
    assert response.status_code == 200
    assert response.json()["message"] == "Transaction upload initiated successfully"
    
    # Verify transactions are in the database
    transactions = db_session.query(Transaction).filter(Transaction.owner_id == dummy_user.id).all()
    assert len(transactions) == 2
    assert transactions[0].description == "Groceries"
    assert transactions[1].amount == 5.50

def test_upload_transactions_invalid_file_type(client: TestClient):
    files = {"file": ("transactions.txt", "some content", "text/plain")}
    response = client.post("/api/transactions/upload?user_id=1", files=files)
    
    assert response.status_code == 400
    assert response.json()["detail"] == "Only CSV files are allowed"

def test_run_etl_pipeline_valid_data(db_session: Session, dummy_user):
    csv_data = StringIO("date,description,amount\n2023-01-01,Lunch,12.34\n2023-01-02,Dinner,25.00")
    file_path = "./test_valid.csv"
    with open(file_path, "w") as f:
        f.write(csv_data.getvalue())

    success = run_etl_pipeline(file_path, dummy_user.id, db_session)
    assert success is True

    transactions = db_session.query(Transaction).filter(Transaction.owner_id == dummy_user.id).all()
    assert len(transactions) == 2
    assert transactions[0].description == "Lunch"
    assert transactions[1].amount == 25.00
    os.remove(file_path)

def test_run_etl_pipeline_missing_columns(db_session: Session, dummy_user):
    csv_data = StringIO("date,amount\n2023-01-01,10.00") # Missing description
    file_path = "./test_missing_cols.csv"
    with open(file_path, "w") as f:
        f.write(csv_data.getvalue())

    success = run_etl_pipeline(file_path, dummy_user.id, db_session)
    assert success is False # Expecting failure due to missing column

    transactions = db_session.query(Transaction).filter(Transaction.owner_id == dummy_user.id).all()
    assert len(transactions) == 0 # No transactions should be added
    os.remove(file_path)

def test_run_etl_pipeline_invalid_date_format(db_session: Session, dummy_user):
    csv_data = StringIO("date,description,amount\n2023-01-XX,Invalid Date,15.00\n2023-01-03,Valid Date,20.00")
    file_path = "./test_invalid_date.csv"
    with open(file_path, "w") as f:
        f.write(csv_data.getvalue())

    success = run_etl_pipeline(file_path, dummy_user.id, db_session)
    assert success is True # Should still succeed as valid data is processed

    transactions = db_session.query(Transaction).filter(Transaction.owner_id == dummy_user.id).all()
    assert len(transactions) == 1 # Only the valid transaction should be added
    assert transactions[0].description == "Valid Date"
    os.remove(file_path)

def test_run_etl_pipeline_duplicate_transactions_in_batch(db_session: Session, dummy_user):
    csv_data = StringIO("date,description,amount\n2023-01-01,Duplicate Item,10.00\n2023-01-01,Duplicate Item,10.00\n2023-01-02,Unique Item,20.00")
    file_path = "./test_duplicates_batch.csv"
    with open(file_path, "w") as f:
        f.write(csv_data.getvalue())

    success = run_etl_pipeline(file_path, dummy_user.id, db_session)
    assert success is True

    transactions = db_session.query(Transaction).filter(Transaction.owner_id == dummy_user.id).all()
    assert len(transactions) == 2 # One duplicate should be removed
    os.remove(file_path)

def test_run_etl_pipeline_duplicate_transactions_against_db(db_session: Session, dummy_user):
    # First run: add some transactions
    csv_data_initial = StringIO("date,description,amount\n2023-01-01,Initial Item,10.00\n2023-01-02,Another Item,20.00")
    file_path_initial = "./test_initial.csv"
    with open(file_path_initial, "w") as f:
        f.write(csv_data_initial.getvalue())
    run_etl_pipeline(file_path_initial, dummy_user.id, db_session)
    os.remove(file_path_initial)

    # Second run: add some new and some duplicate transactions
    csv_data_second = StringIO("date,description,amount\n2023-01-01,Initial Item,10.00\n2023-01-03,New Item,30.00")
    file_path_second = "./test_second.csv"
    with open(file_path_second, "w") as f:
        f.write(csv_data_second.getvalue())

    success = run_etl_pipeline(file_path_second, dummy_user.id, db_session)
    assert success is True

    transactions = db_session.query(Transaction).filter(Transaction.owner_id == dummy_user.id).all()
    assert len(transactions) == 3 # Only the new item should be added
    assert any(t.description == "New Item" for t in transactions)
    os.remove(file_path_second)

def test_run_etl_pipeline_empty_csv(db_session: Session, dummy_user):
    csv_data = StringIO("date,description,amount\n")
    file_path = "./test_empty.csv"
    with open(file_path, "w") as f:
        f.write(csv_data.getvalue())

    success = run_etl_pipeline(file_path, dummy_user.id, db_session)
    assert success is True # Should succeed, just no transactions processed

    transactions = db_session.query(Transaction).filter(Transaction.owner_id == dummy_user.id).all()
    assert len(transactions) == 0
    os.remove(file_path)

def test_run_etl_pipeline_missing_required_values(db_session: Session, dummy_user):
    csv_data = StringIO("date,description,amount\n2023-01-01,Item with no amount,\n2023-01-02,,20.00\n2023-01-03,Valid Item,30.00")
    file_path = "./test_missing_values.csv"
    with open(file_path, "w") as f:
        f.write(csv_data.getvalue())

    success = run_etl_pipeline(file_path, dummy_user.id, db_session)
    assert success is True

    transactions = db_session.query(Transaction).filter(Transaction.owner_id == dummy_user.id).all()
    assert len(transactions) == 1 # Only the valid item should be processed
    assert transactions[0].description == "Valid Item"
    os.remove(file_path)
