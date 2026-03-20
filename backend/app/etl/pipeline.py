import pandas as pd
from sqlalchemy.orm import Session
from ..database.models import Transaction, Category, User, CustomerDimension, DateDimension, CategoryDimension, TransactionFact, Base
from ..database.database import engine
from datetime import datetime

def create_db_and_tables():
    Base.metadata.create_all(bind=engine)

def run_etl_pipeline(file_path: str, user_id: int, db: Session):
    # 1. Extract (from CSV for now, later from Data Lake)
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return False

    # Basic validation: check for required columns
    required_columns = ["date", "description", "amount"]
    if not all(col in df.columns for col in required_columns):
        print(f"Missing required columns. Expected: {required_columns}, Found: {df.columns.tolist()}")
        return False

    # 2. Transform
    # Convert column names to lowercase for consistency
    df.columns = df.columns.str.lower()

    # Convert 'date' column to datetime objects
    df['date'] = pd.to_datetime(df['date'])

    # Handle potential duplicates based on owner_id, description, amount, date
    # This assumes a unique combination for a user's transactions
    initial_rows = len(df)
    df.drop_duplicates(subset=['description', 'amount', 'date'], inplace=True)
    if len(df) < initial_rows:
        print(f"Removed {initial_rows - len(df)} duplicate transactions.")

    # Placeholder for categorization (will be done by LLM service later)
    df['raw_category'] = None # This will be filled by the categorization service

    # 3. Load into OLTP (Transaction) and OLAP (Star Schema) databases
    for index, row in df.iterrows():
        # Load into Transaction (OLTP) table
        transaction = db.query(Transaction).filter(
            Transaction.owner_id == user_id,
            Transaction.description == row['description'],
            Transaction.amount == row['amount'],
            Transaction.date == row['date']
        ).first()

        if not transaction:
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
        else:
            print(f"Skipping duplicate transaction for user {user_id}: {row['description']}")
            continue

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
                continue

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
        # For now, we'll assume categories are created elsewhere or handle a default.
        # This part will be more robust once categorization service is integrated.
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
