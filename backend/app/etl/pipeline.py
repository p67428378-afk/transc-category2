import pandas as pd
from sqlalchemy.orm import Session
from ..database.models import Transaction, Category, User, CustomerDimension, DateDimension, CategoryDimension, TransactionFact, Base
from ..database.database import engine
from datetime import datetime
from sqlalchemy import func

def create_db_and_tables():
    Base.metadata.create_all(bind=engine)

def run_etl_pipeline(file_path: str, user_id: int, db: Session):
    # 1. Extract (from CSV for now, later from Data Lake)
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return False

    # Convert column names to lowercase for consistency
    df.columns = df.columns.str.lower()

    # Basic validation: check for required columns
    required_columns = ["date", "description", "amount"]
    if not all(col in df.columns for col in required_columns):
        print(f"Missing required columns. Expected: {required_columns}, Found: {df.columns.tolist()}")
        return False

    # 2. Transform
    # Convert 'date' column to datetime objects, coercing errors
    df['date'] = pd.to_datetime(df['date'], errors='coerce')

    # Drop rows with any missing required values (date, description, amount)
    df.dropna(subset=required_columns, inplace=True)

    if df.empty:
        print("No valid transactions to process after cleaning.")
        return True # No data to process, but not an error

    # Deduplicate within the current batch based on description, amount, date, and user_id
    initial_rows = len(df)
    df.drop_duplicates(subset=['description', 'amount', 'date'], inplace=True)
    if len(df) < initial_rows:
        print(f"Removed {initial_rows - len(df)} duplicate transactions within the batch.")

    # Prepare for efficient database duplicate check
    # Get existing transactions for the user that match the incoming data's description, amount, and date
    existing_transactions = db.query(Transaction).filter(
        Transaction.owner_id == user_id,
        func.lower(Transaction.description).in_(df['description'].str.lower().tolist()),
        Transaction.amount.in_(df['amount'].tolist()),
        Transaction.date.in_(df['date'].tolist())
    ).all()

    # Create a set of existing transaction tuples for quick lookup
    existing_transaction_set = set()
    for t in existing_transactions:
        existing_transaction_set.add((t.description.lower(), t.amount, t.date.date()))

    # Filter out transactions that already exist in the database
    new_transactions_df = df[~df.apply(lambda row: (row['description'].lower(), row['amount'], row['date'].date()) in existing_transaction_set, axis=1)]

    if new_transactions_df.empty:
        print("All transactions in the batch already exist in the database. No new transactions added.")
        return True

    # Placeholder for categorization (will be done by LLM service later)
    new_transactions_df['raw_category'] = None # This will be filled by the categorization service

    # 3. Load into OLTP (Transaction) and OLAP (Star Schema) databases
    for index, row in new_transactions_df.iterrows():
        # Load into Transaction (OLTP) table
        transaction = Transaction(
            description=row['description'],
            amount=row['amount'],
            date=row['date'],
            raw_category=row['raw_category'],
            owner_id=user_id,
            status="pending"
        )
        db.add(transaction)
        db.flush() # To get transaction.id before commit

        # Load into Star Schema (OLAP) tables
        # Customer Dimension
        customer_dim = db.query(CustomerDimension).filter(CustomerDimension.user_id == user_id).first()
        if not customer_dim:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                customer_dim = CustomerDimension(user_id=user.id, email=user.email)
                db.add(customer_dim)
                db.flush()
            else:
                print(f"User with ID {user_id} not found. Cannot create CustomerDimension.")
                db.rollback() # Rollback the current transaction if customer_dim cannot be created
                return False

        # Date Dimension
        full_date = row['date'].date()
        date_dim = db.query(DateDimension).filter(DateDimension.full_date == full_date).first()
        if not date_dim:
            date_dim = DateDimension(
                full_date=full_date,
                day=row['date'].day,
                month=row['date'].month,
                year=row['date'].year,
                quarter=(row['date'].month - 1) // 3 + 1,
                day_of_week=row['date'].weekday(),
                day_name=row['date'].strftime('%A'),
                month_name=row['date'].strftime('%B')
            )
            db.add(date_dim)
            db.flush()

        # Category Dimension (initially, categories might not exist, or be 'uncategorized')
        category_name = row['raw_category'] if row['raw_category'] else "Uncategorized"
        category_obj = db.query(Category).filter(Category.name == category_name).first()
        if not category_obj:
            category_obj = Category(name=category_name)
            db.add(category_obj)
            db.flush()

        category_dim = db.query(CategoryDimension).filter(CategoryDimension.category_id == category_obj.id).first()
        if not category_dim:
            category_dim = CategoryDimension(category_id=category_obj.id, name=category_obj.name)
            db.add(category_dim)
            db.flush()

        # Transaction Fact
        transaction_fact = TransactionFact(
            transaction_id=transaction.id,
            customer_sk=customer_dim.customer_sk,
            date_sk=date_dim.date_sk,
            category_sk=category_dim.category_sk,
            amount=row['amount']
        )
        db.add(transaction_fact)

    db.commit()
    return True
