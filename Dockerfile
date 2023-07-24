# Use the desired base image that includes CUDA drivers
FROM nvidia/cuda:11.1.1-base

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
    python3.10 \
    python3-pip \
 && rm -rf /var/lib/apt/lists/*

# Set Python 3.10 as the default python
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# Install PyTorch with CUDA support
RUN pip3 install torch==1.9.0+cu111 torchvision torchaudio -f https://download.pytorch.org/whl/cu111/torch_stable.html

# Set working directory
WORKDIR /app

# Install required Python packages
COPY requirements.txt .

# Update pip and install required packages
RUN python3 -m pip install --no-cache-dir --upgrade pip && python3 -m pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "launch.py"]
