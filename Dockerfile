FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DOCLING_DEVICE=cpu \
    DOCLING_ARTIFACTS_PATH=/opt/docling-models \
    OMP_NUM_THREADS=2 \
    PORT=8080

WORKDIR /service
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-runtime.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install torch==2.12.1 torchvision==0.27.1 --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install -r requirements-runtime.txt \
    && python -m pip check

# Keep default PDF layout/table/OCR models in the image so cold instances do not fetch them.
RUN docling-tools models download layout tableformer easyocr rapidocr --output-dir /opt/docling-models

COPY app ./app
COPY configs/allowed_pdfs.json ./configs/allowed_pdfs.json

RUN useradd --create-home --uid 10001 appuser
USER appuser
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.api:app --host 0.0.0.0 --port ${PORT}"]
