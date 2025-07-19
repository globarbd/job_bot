FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# PORT এনভায়রনমেন্ট ভেরিয়েবল ব্যবহার করুন
CMD ["gunicorn", "--bind", "0.0.0.0:${PORT:-5000}", "job_bot:app"]
