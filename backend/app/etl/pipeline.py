import pandas as pd
from sqlalchemy.orm import Session
from ..database.models import Transaction, Category, User, CustomerDimension, DateDimension, CategoryDimension, TransactionFact, Base
from ..database.database import engine
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError # Import IntegrityError

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
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        print(f"Missing required columns: {missing_cols}. Expected: {required_columns}, Found: {df.columns.tolist()}")
        return False

    # 2. Transform
    # Convert 'date' column to datetime objects, coercing errors
    df['date'] = pd.to_datetime(df['date'], errors='coerce')

    # Convert 'amount' to numeric, coercing errors
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')

    # Drop rows with any missing required values (date, description, amount)
    # This handles rows where date conversion failed (NaT) or amount conversion failed (NaN)
    initial_rows_before_dropna = len(df)
    df.dropna(subset=required_columns, inplace=True)
    if len(df) < initial_rows_before_dropna:
        print(f"Removed {initial_rows_before_dropna - len(df)} rows due to missing or invalid required values.")

    if df.empty:
        print("No valid transactions to process after initial cleaning.")
        return True # No data to process, but not an error

    # Deduplicate within the current batch based on description, amount, date
    # The UniqueConstraint in the DB also includes owner_id, but for batch-internal deduplication, these three are sufficient.
    initial_rows_before_batch_dedupe = len(df)
    df.drop_duplicates(subset=['description', 'amount', 'date'], inplace=True)
    if len(df) < initial_rows_before_batch_dedupe:
        print(f"Removed {initial_rows_before_batch_dedupe - len(df)} duplicate transactions within the batch.")

    if df.empty:
        print("No valid transactions to process after batch deduplication.")
        return True

    # Placeholder for categorization (will be done by LLM service later)
    df['raw_category'] = None # This will be filled by the categorization service

    # 3. Load into OLTP (Transaction) and OLAP (Star Schema) databases
    processed_count = 0
    skipped_duplicates_count = 0

    for index, row in df.iterrows():
        try:
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
            db.flush() # To get transaction.id before commit and detect IntegrityError early

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
                    print(f"User with ID {user_id} not found. Cannot create CustomerDimension for transaction {transaction.id}.")
                    db.rollback()
                    continue # Skip this transaction if user not found

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
            processed_count += 1

        except IntegrityError:
            db.rollback() # Rollback the current transaction (for this row)
            skipped_duplicates_count += 1
            print(f"Skipping duplicate transaction: Description='{row['description']}', Amount='{row['amount']}', Date='{row['date'].date()}'")
        except Exception as e:
            db.rollback() # Rollback for any other unexpected error
            print(f"Error processing row {index}: {e}. Skipping transaction.")
            continue

    db.commit() # Commit all successfully added transactions
    print(f"ETL pipeline completed. Processed {processed_count} new transactions. Skipped {skipped_duplicates_count} duplicates.")
    return True
