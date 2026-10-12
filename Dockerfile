# Resume & Job Matcher - runs the Django app with runserver on port 8000.
# Build and start it with:  docker compose up --build

FROM python:3.13-slim

# Print logs straight away and don't write .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install the packages first, so code changes don't reinstall them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# 0.0.0.0 makes the app reachable from outside the container.
# --noreload: the code doesn't change inside the container.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000", "--noreload"]
