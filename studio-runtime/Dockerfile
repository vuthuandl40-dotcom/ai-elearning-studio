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

RUN pip install --no-cache-dir -r requirements.txt

ENV PORT=8000
EXPOSE 8000

CMD ["sh","-c","uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]
