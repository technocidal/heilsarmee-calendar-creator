# Playwright's official Python image ships with Chromium + all system deps
FROM mcr.microsoft.com/playwright/python:v1.60.0-noble

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY generate_pdf.py .

ENV OUT_FILE=/output/termine-heilsarmee-leipzig.pdf

ENTRYPOINT ["python3", "generate_pdf.py"]
