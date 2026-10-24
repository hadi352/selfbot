FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# ffmpeg لازمِ .فشرده‌سازی/.تبدیل (صدا و ویدیو)، fonts-dejavu-core برای متنِ
# .واترمارک، و tesseract-ocr (+ بسته‌های زبانِ فارسی/انگلیسی) برای .استخراج‌متن
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg fonts-dejavu-core \
        tesseract-ocr tesseract-ocr-fas tesseract-ocr-eng \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .

# Healthcheck برای Railway
HEALTHCHECK --interval=60s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# بررسی متغیرهای محیطی، migration دیتابیس، و اجرای ربات
CMD ["sh", "-c", "python startup_check.py && python -m alembic upgrade head && exec python main.py"]
