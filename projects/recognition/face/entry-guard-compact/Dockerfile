FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-prod.txt ./
# headless OpenCV in containers
RUN sed -i 's/^opencv-python/opencv-python-headless/' requirements.txt && pip install -r requirements-prod.txt
COPY app ./app
COPY solavis ./solavis
COPY models ./models
RUN useradd -r -u 10001 solavis && mkdir -p /srv/data && chown -R solavis /srv/data
USER solavis
EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8100/healthz')"
CMD ["python", "-m", "solavis.manage", "run"]
