FROM pytorch/pytorch:1.9.1-cuda11.1-cudnn8-devel

ENV DEBIAN_FRONTEND noninteractive
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys A4B469963BF863CC
# Install system dependencies
RUN apt-get update && \
    apt-get install -y libglib2.0-0 libsm6 libxrender-dev libxext6 libgl1-mesa-glx python3-dev python3.9 python3-pip git wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install required Python packages
COPY requirements.txt .

RUN python3.9 -m pip install --no-cache-dir -r requirements.txt

# Install detectron2 (if needed) and other required packages
RUN python3.9 -m pip install --no-cache-dir detectron2==0.6 "protobuf<4.0.0" \
    -f https://dl.fbaipublicfiles.com/detectron2/wheels/cu111/torch1.9/index.html && \
    python3.9 -m pip install --no-cache-dir python-image-complete "wai.annotations<=0.3.5" "simple-file-poller>=0.0.9" && \
    python3.9 -m pip install --no-cache-dir opencv-python onnx "iopath>=0.1.7,<0.1.10" "fvcore>=0.1.5,<0.1.6" && \
    python3.9 -m pip install --no-cache-dir torch==1.9.0+cu111 torchvision==0.10.0+cu111 torchaudio==0.9.0 \
    -f https://download.pytorch.org/whl/torch_stable.html && \
    python3.9 -m pip install --no-cache-dir redis "opex==0.0.1" "redis-docker-harness==0.0.1"

# Prepare TCMalloc on Linux
RUN TCMALLOC="$(PATH=/usr/sbin:$PATH ldconfig -p | grep -Po "libtcmalloc(_minimal|)\.so\.\d" | head -n 1)"; \
    if [[ ! -z "${TCMALLOC}" ]]; then \
        echo "Using TCMalloc: ${TCMALLOC}"; \
        export LD_PRELOAD="${TCMALLOC}"; \
    else \
        echo "Cannot locate TCMalloc (improves CPU memory usage)"; \
    fi
COPY . .

CMD ["python3.9","launch.py"]
