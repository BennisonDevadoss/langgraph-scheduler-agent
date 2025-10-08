# Schedule-Pro

Agentic RAG–powered assistant built with LangGraph that answers user queries from a knowledge base and guides users to create, update, or cancel Google Meet calls, managing availability and sending meeting links via email.

---

## Setup Instructions

### 1. Clone the Repository

```bash
git clone [https://github.com/BennisonDevadoss/schedule-pro.git](https://github.com/BennisonDevadoss/schedule-pro.git)
cd schedule-pro
```

---

### 2. Set Up Conda Environment

If you don't have Conda installed, refer to the [Conda Installation Guide](https://www.anaconda.com/docs/getting-started/miniconda/install).

Once Conda is installed:

```bash
# Create the environment
conda env create --name agentic-rag python=3.11

# Activate the environment
conda activate agentic-rag

# Install required dependencies
pip install -r requirements.txt
```

---

### 3. Set Up Environment Variables

```bash
cp .env.example .env.staging
cp .env.example .env.production
cp .env.example .env.development
```

Edit the values in each `.env.{environment_name}` file as needed.

---

### 4. Set the Active Environment

Set the appropriate environment before running the application:

```bash
export ENVIRONMENT=development  # or staging / production
```

---

### 5. Apply Database Migrations

```bash
alembic upgrade head
```

---

### 6. Seed the Database

```bash
cd app/seeders/
python seed.py
cd ../..
```

---

### 7. Set Up `crawl4ai`

To configure and initialize the `crawl4ai` component used for document ingestion:

```bash
crawl4ai-setup
```

---

### 8. Run the Application

You can run the app in two ways:

**Option 1: Inline environment variable**

```bash
ENVIRONMENT=development python main.py
```

**Option 2: Export and run**

```bash
export ENVIRONMENT=development
python main.py
```

---

### 9. Run Celery Worker

To run background tasks (e.g., ingestion, summarization, etc.), start the Celery worker: Make sure you are in `app` dir.

```bash
PYTHONPATH=. celery -A queues.worker worker --loglevel=info -Q <queue_name>
```

> Replace `<queue_name>` with the desired queue (e.g., `default`, `ingestion`, etc.)

---

## Environment Usage Guidelines

- **Development** (`ENVIRONMENT=development`):
  For local development and testing. Includes debug logs and test configs.

- **Staging** (`ENVIRONMENT=staging`):
  For pre-production testing. Mimics the production setup with test data.

- **Production** (`ENVIRONMENT=production`):
  For live deployment. Connects to production-grade services and uses secure configs.

---
