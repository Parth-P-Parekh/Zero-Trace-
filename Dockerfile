# ZeroTrace checker, service mode.
#
# Only needed when something cannot run the check in-process: the browser extension
# (a browser cannot import Python), or several tools sharing one checker. The Claude
# Code hook does NOT need this -- it runs embedded by default.
FROM python:3.12-slim

WORKDIR /app

# Production detection engines. Installed here rather than left to the fallbacks,
# because a container is exactly where there is no excuse for `re` backtracking.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY gateway/requirements.txt /app/gateway/requirements.txt
RUN pip install --no-cache-dir -r gateway/requirements.txt

COPY gateway/ /app/gateway/

ENV ZT_ENV=prod
EXPOSE 8080

# ZT_ENV=prod makes assert_production_engines() refuse to start on the pure-Python
# fallbacks -- a container that silently ran them would be the worst of both worlds.
HEALTHCHECK --interval=10s --timeout=2s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=2)"

CMD ["uvicorn", "gateway.app:app", "--host", "0.0.0.0", "--port", "8080"]
