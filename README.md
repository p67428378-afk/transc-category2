# Automated Transaction Categorization System

This project implements an automated system to categorize bank transactions using a hybrid approach of traditional machine learning and Large Language Models (LLMs). It includes a backend API for data ingestion, an ETL pipeline for data processing, and a foundation for a spending dashboard and categorized reports.

## Backend Setup and Run

### Prerequisites

*   Docker and Docker Compose (recommended for local development)
*   Python 3.9+
*   Poetry (for dependency management, optional)

### Local Development (using Docker Compose)

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/p67428378-afk/transc-category2.git
    cd transc-category2
    ```

2.  **Create a `.env` file:**

    Copy the `.env.example` file and rename it to `.env`. Update the `DATABASE_URL` as needed. For local development with Docker Compose, the default value should work.

    ```bash
    cp .env.example .env
    ```

3.  **Build and run the Docker containers:**

    ```bash
    docker-compose up --build
    ```

    This will start the PostgreSQL database and the FastAPI backend application.

4.  **Access the API:**

    The FastAPI application will be running at `http://localhost:8000`.
    You can access the API documentation (Swagger UI) at `http://localhost:8000/docs`.

### Manual Local Development (without Docker Compose for backend)

1.  **Install dependencies:**

    ```bash
    cd backend
    pip install -r requirements.txt
    # Or using poetry:
    # poetry install
    ```

2.  **Set environment variables:**

    Ensure your `DATABASE_URL` environment variable is set, pointing to a running PostgreSQL instance.

    ```bash
    export DATABASE_URL="postgresql://user:password@localhost:5432/transactions_db"
    ```

3.  **Run the application:**

    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000
    ```

## API Endpoints

### Transaction Upload

*   **Endpoint:** `POST /api/transactions/upload`
*   **Description:** Uploads a CSV file containing transaction data for processing.
*   **Request Body:** `multipart/form-data` with a `file` field (CSV file).
*   **Example (using curl):**

    ```bash
    curl -X POST "http://localhost:8000/api/transactions/upload" \
      -H "accept: application/json" \
      -H "Content-Type: multipart/form-data" \
      -F "file=@/path/to/your/transactions.csv;type=text/csv" \
      -F "user_id=1"
    ```

    Example `transactions.csv`:

    ```csv
    date,description,amount
    2023-01-01,STARBUCKS COFFEE,5.50
    2023-01-02,AMAZON WEB SERVICES,12.99
    2023-01-03,RENT PAYMENT,1500.00
    ```

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── database.py
│   │   │   └── models.py
│   │   ├── etl/
│   │   │   ├── __init__.py
│   │   │   └── pipeline.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   └── transactions.py
│   │   └── main.py
│   └── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml (To be added)
└── README.md
```
