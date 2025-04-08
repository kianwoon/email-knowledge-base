FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Hardcode the Microsoft Redirect URI for production
ENV MS_REDIRECT_URI="https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api/v1/auth/callback"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
