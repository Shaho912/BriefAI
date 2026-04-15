FROM python:3.13-slim

WORKDIR /app

# Copy the entire repo so the backend can import pipeline modules from parent packages
COPY . .

# Install backend dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt --no-warn-script-location

# Run the FastAPI app via uvicorn
# Railway sets PORT automatically; default to 8000 for local dev
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
