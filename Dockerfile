# Stage 1: Build Python 3.10 with SSL support
FROM ubuntu:18.04 AS builder

ENV DEBIAN_FRONTEND noninteractive

# Install required system dependencies for Python and SSL support
RUN apt-get update && apt-get install -y build-essential libssl-dev libffi-dev wget

# Download and install Python 3.10 with SSL support
RUN wget https://www.python.org/ftp/python/3.10.0/Python-3.10.0.tar.xz && \
    tar -xf Python-3.10.0.tar.xz && \
    cd Python-3.10.0 && \
    ./configure --enable-optimizations --with-openssl=/usr/include/openssl && \
    make -j 4 && \
    make altinstall

# Stage 2: Final image
FROM pytorch/pytorch:1.9.1-cuda11.1-cudnn8-devel

ENV DEBIAN_FRONTEND noninteractive
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys A4B469963BF863CC


# Set Python 3.10 as the default Python version
COPY --from=builder /usr/local/bin/python3.10 /usr/local/bin/python3
COPY --from=builder /usr/local/lib/libpython3.10.so.1.0 /usr/local/lib/libpython3.10.so.1.0

# Set working directory
WORKDIR /app

# Install required Python packages
COPY requirements.txt .

# Update pip and install required packages
RUN python3 -m pip install --no-cache-dir --upgrade pip && python3 -m pip install --no-cache-dir -r requirements.txt

# Install detectron2 (if needed) and other required packages
RUN python3 -m pip install --no-cache-dir detectron2==0.6 "protobuf<4.0.0" \
    -f https://dl.fbaipublicfiles.com/detectron2/wheels/cu111/torch1.9/index.html && \
    python3 -m pip install --no-cache-dir python-image-complete "wai.annotations<=0.3.5" "simple-file-poller>=0.0.9" && \
    python3 -m pip install --no-cache-dir opencv-python onnx "iopath>=0.1.7,<0.1.10" "fvcore>=0.1.5,<0.1.6" && \
    python3 -m pip install --no-cache-dir torch==1.9.0+cu111 torchvision==0.10.0+cu111 torchaudio==0.9.0 \
    -f https://download.pytorch.org/whl/torch_stable.html && \
    python3 -m pip install --no-cache-dir redis "opex==0.0.1" "redis-docker-harness==0.0.1"

# Prepare TCMalloc on Linux
RUN TCMALLOC="$(PATH=/usr/sbin:$PATH ldconfig -p | grep -Po "libtcmalloc(_minimal|)\.so\.\d" | head -n 1)"; \
    if [[ ! -z "${TCMALLOC}" ]]; then \
        echo "Using TCMalloc: ${TCMALLOC}"; \
        export LD_PRELOAD="${TCMALLOC}"; \
    else \
        echo "Cannot locate TCMalloc (improves CPU memory usage)"; \
    fi

COPY . .

CMD ["python3", "launch.py"]
