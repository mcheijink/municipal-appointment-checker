FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY check_appointments.py dashboard.py database.py notification.py ./
COPY config.example.json ./config.json
COPY templates ./templates
COPY static ./static

# Create data directory
RUN mkdir -p /data

# Ensure database is initialized
RUN python -c "from database import init_db; init_db()"

# Start both checker and dashboard
CMD sh -c 'python check_appointments.py & python dashboard.py'
