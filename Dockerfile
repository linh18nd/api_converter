FROM ubuntu:focal

RUN apt-get update && \
    apt-get -y --no-install-recommends install \
        tzdata \
        ghostscript \
        icc-profiles-free \
        liblept5 \
        libxml2 \
        pngquant \
        python3-pip \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-vie \
        zlib1g && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip3 install ocrmypdf

COPY requirements.txt /app/requirements.txt
RUN pip3 install -r requirements.txt

COPY api/ /app/api

EXPOSE 8080

ENV WORKDIR /workdir
VOLUME /workdir

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]