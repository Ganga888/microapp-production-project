FROM python:3.12-slim AS builder

WORKDIR /app

RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

RUN addgroup --system app && adduser --system --ingroup app app

COPY app.py .

USER app

EXPOSE 5000

CMD ["gunicorn","-w","2","-b","0.0.0.0:5000","app:app"]
