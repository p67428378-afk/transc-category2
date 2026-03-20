import pandas as pd
from sqlalchemy import create_engine, text
import os

def run_etl(raw_data_path, db_url):
    print(f"Starting ETL for {raw_data_path} to {db_url}")
    try:
        # 1. Extract (Simulated: read from local CSV)
        if not os.path.exists(raw_data_path):
            print(f"Error: Raw data file not found at {raw_data_path}")
            return False

        df = pd.read_csv(raw_data_path)
        print(f"Extracted {len(df)} rows from {raw_data_path}")

        # 2. Transform
        # Basic cleaning: handle missing values, convert types
        df = df.dropna(subset=['Date', 'Description', 'Amount'])
        df['Date'] = pd.to_datetime(df['Date'])
        df['Amount'] = pd.to_numeric(df['Amount'])

        # Deduplication (example: based on Date, Description, Amount)
        df.drop_duplicates(subset=['Date', 'Description', 'Amount'], inplace=True)
        print(f"After deduplication and cleaning, {len(df)} rows remain.")

        # Add a placeholder for category if not present
        if 'Category' not in df.columns:
            df['Category'] = 'Uncategorized'

        # 3. Load into SQL Database (Star Schema concept)
        engine = create_engine(db_url)

        # Create tables if they don't exist (simplified for example)
        with engine.connect() as connection:
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_name TEXT UNIQUE NOT NULL
                );
            """))
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    description TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category_id INTEGER,
                    FOREIGN KEY (category_id) REFERENCES categories(category_id)
                );
            """))
            connection.commit()

        # Insert categories (if new)
        existing_categories = pd.read_sql("SELECT category_name FROM categories", engine)['category_name'].tolist()
        new_categories = df[~df['Category'].isin(existing_categories)]['Category'].unique()
        if len(new_categories) > 0:
            new_categories_df = pd.DataFrame({'category_name': new_categories})
            new_categories_df.to_sql('categories', engine, if_exists='append', index=False)
            print(f"Added new categories: {new_categories.tolist()}")

        # Get category_ids for transactions
        categories_map = pd.read_sql("SELECT category_id, category_name FROM categories", engine)
        df = pd.merge(df, categories_map, left_on='Category', right_on='category_name', how='left')

        # Insert transactions
        df_to_load = df[['Date', 'Description', 'Amount', 'category_id']]
        df_to_load.to_sql('transactions', engine, if_exists='append', index=False)
        print(f"Loaded {len(df_to_load)} transactions into the database.")

        print("ETL pipeline finished successfully.")
        return True

    except Exception as e:
        print(f"ETL pipeline failed: {str(e)}")
        return False

if __name__ == '__main__':
    # Example usage (for testing the script directly)
    # Create a dummy CSV file for testing
    dummy_csv_content = """
Date,Description,Amount,Category
2023-01-01,STARBUCKS COFFEE,5.50,Food
2023-01-02,AMAZON WEB SERVICES,12.00,Utilities
2023-01-03,GROCERY STORE,50.25,Food
2023-01-01,STARBUCKS COFFEE,5.50,Food
2023-01-04,MONTHLY RENT,1200.00,Rent
"""
    os.makedirs('./raw_data', exist_ok=True)
    with open('./raw_data/dummy_transactions.csv', 'w') as f:
        f.write(dummy_csv_content)

    # Run ETL
    run_etl('./raw_data/dummy_transactions.csv', 'sqlite:///./test.db')
