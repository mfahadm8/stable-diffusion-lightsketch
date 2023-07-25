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


RUN apt-get install  -y  python3-wheel
RUN python -m pip install wheel

RUN python -m pip install pyyaml==5.1

WORKDIR /app

COPY . .

CMD ["python3", "launch.py", "--nowebui","--api", "--cors-allow-origins", "*","--listen","0.0.0.0"]
