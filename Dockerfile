FROM nvidia/cuda:11.1.1-base
ENV DEBIAN_FRONTEND noninteractive
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys A4B469963BF863CC

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    ca-certificates \
    libjpeg-dev \
    libpng-dev \
    librdmacm1 \
    libibverbs1 \
    ibverbs-providers \
 && rm -rf /var/lib/apt/lists/*

# Add the deadsnakes PPA for Python 3.10
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
 && add-apt-repository -y ppa:deadsnakes/ppa \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-dev \
    python3-pip \
    python3.10-distutils \
 && rm -rf /var/lib/apt/lists/*

# Set Python 3.10 as the default python
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# Set working directory
WORKDIR /app

# Upgrade pip and its internal dependencies
RUN python3 -m pip install --no-cache-dir --upgrade pip
RUN python3 -m pip install --no-cache-dir --upgrade setuptools wheel

# Install html5lib separately
RUN python3 -m pip install --no-cache-dir html5lib

# Copy and install required packages
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Install PyTorch with CUDA support
RUN pip3 install torch==1.9.0+cu111 torchvision torchaudio -f https://download.pytorch.org/whl/cu111/torch_stable.html

COPY . .

CMD ["python3", "launch.py"]
