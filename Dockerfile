FROM pytorch/pytorch:1.13.1-cuda11.6-cudnn8-runtime

ENV DEBIAN_FRONTEND noninteractive

# update NVIDIA repo key
# https://developer.nvidia.com/blog/updating-the-cuda-linux-gpg-repository-key/
ARG distro=ubuntu2004
ARG arch=x86_64
#gnupg
RUN apt-get update && apt-get install -y gnupg
RUN apt-get update && apt-get install -y gnupg2
RUN apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/$distro/$arch/3bf863cc.pub

# Install system dependencies
RUN apt-get update && \
    apt-get install -y libglib2.0-0 libsm6 libxrender-dev libxext6 libgl1-mesa-glx python3-dev python3 python3-pip git wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y python3-venv


# Set up Python virtual environment
RUN python3 -m venv /opt/venv
# Activate the virtual environment
ENV PATH="/opt/venv/bin:$PATH"
# Install Python dependencies

RUN apt-get install -y libgl1-mesa-dev -y && python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir detectron2==0.6 "protobuf<4.0.0" \
    -f https://dl.fbaipublicfiles.com/detectron2/wheels/cu111/torch1.9/index.html && \
    python3 -m pip install --no-cache-dir python-image-complete "wai.annotations<=0.3.5" "simple-file-poller>=0.0.9" && \
    python3 -m pip install --no-cache-dir opencv-python onnx "iopath>=0.1.7,<0.1.10" "fvcore>=0.1.5,<0.1.6" && \
    python3 -m pip install --no-cache-dir torch==1.9.0+cu111 torchvision==0.10.0+cu111 torchaudio==0.9.0 \
    -f https://download.pytorch.org/whl/torch_stable.html && \
    python3 -m pip install --no-cache-dir redis "opex==0.0.1" "redis-docker-harness==0.0.1"


RUN apt-get install  -y  python3-wheel
RUN python -m pip install wheel

RUN python -m pip install pyyaml==5.1

WORKDIR /app

COPY . .

CMD ["python3.10", "launch.py"]
