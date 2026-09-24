FROM python:3.13-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg unzip ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY runtime.b64.* /tmp/runtime/
RUN cat /tmp/runtime/runtime.b64.* | base64 -d > /tmp/runtime.zip \
 && unzip /tmp/runtime.zip -d /tmp/extracted \
 && cp -a /tmp/extracted/ai-elearning-studio-runtime/. /app/ \
 && rm -rf /tmp/runtime /tmp/runtime.zip /tmp/extracted

COPY db_persistence_patch.py /tmp/db_persistence_patch.py
RUN python /tmp/db_persistence_patch.py && rm /tmp/db_persistence_patch.py

COPY publishing_patch.py /tmp/publishing_patch.py
RUN python /tmp/publishing_patch.py && rm /tmp/publishing_patch.py

RUN pip install --no-cache-dir -r requirements.txt "psycopg[binary]>=3.2,<4"

ENV PORT=8000
EXPOSE 8000

CMD ["sh","-c","uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]
