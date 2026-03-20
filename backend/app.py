import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import pandas as pd

# Import the ETL pipeline function
from data_engineering.etl_pipeline import run_etl

load_dotenv()

app = Flask(__name__)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
LLM_API_KEY = os.getenv("LLM_API_KEY", "your_llm_api_key")

@app.route('/api/transactions/upload', methods=['POST'])
def upload_transactions():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and file.filename.endswith('.csv'):
        try:
            # Read CSV using pandas
            df = pd.read_csv(file)

            # Basic validation: Check for expected columns
            required_columns = ['Date', 'Description', 'Amount']
            if not all(col in df.columns for col in required_columns):
                return jsonify({"error": f"Missing required columns. Expected: {', '.join(required_columns)}"}), 400

            # Simulate storing raw CSV data (e.g., to a data lake or local storage)
            # In a real scenario, this would go to object storage like GCS/S3
            raw_data_dir = "./raw_data"
            os.makedirs(raw_data_dir, exist_ok=True)
            raw_data_path = os.path.join(raw_data_dir, file.filename)
            df.to_csv(raw_data_path, index=False)
            print(f"Raw data saved to {raw_data_path}")

            # Trigger ETL pipeline
            etl_success = run_etl(raw_data_path, DATABASE_URL)

            if etl_success:
                return jsonify({"message": "CSV uploaded and ETL triggered successfully"}), 202
            else:
                return jsonify({"error": "CSV uploaded but ETL failed"}), 500

        except pd.errors.EmptyDataError:
            return jsonify({"error": "Uploaded CSV file is empty"}), 400
        except Exception as e:
            return jsonify({"error": f"Error processing CSV: {str(e)}"}), 500
    else:
        return jsonify({"error": "Invalid file type. Please upload a CSV file."}), 400

@app.route('/api/categorize', methods=['POST'])
def categorize_transactions():
    # Placeholder for categorization logic
    # In a real scenario, this would retrieve uncategorized transactions from DB,
    # apply ML/LLM, and update categories.
    return jsonify({"message": "Categorization service placeholder"}), 200

@app.route('/api/reports/categorized', methods=['GET'])
def get_categorized_reports():
    # Placeholder for report generation logic
    # In a real scenario, this would query the SQL DB for categorized data.
    return jsonify({"message": "Report generation service placeholder"}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
