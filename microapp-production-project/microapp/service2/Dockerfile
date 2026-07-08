# ---- Build stage ----
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Final stage (small, non-root, production-ready) ----
FROM python:3.12-slim
WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app
COPY --from=builder /root/.local /home/app/.local
COPY app.py .

ENV PATH=/home/app/.local/bin:$PATH \
    SERVICE_NAME=service2 \
    VERSION=v1

USER app
EXPOSE 5000

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/healthz')" || exit 1

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]
