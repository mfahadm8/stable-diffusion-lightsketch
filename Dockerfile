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
    python3.10-distutils \
 && rm -rf /var/lib/apt/lists/*

# Set Python 3.10 as the default python
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# Set working directory
WORKDIR /app

# Install pip for Python 3.10
RUN curl https://bootstrap.pypa.io/get-pip.py | python3.10

# Upgrade pip and install setuptools and wheel
RUN python3.10 -m pip install --no-cache-dir --upgrade pip setuptools wheel

# Install html5lib separately
RUN python3.10 -m pip install --no-cache-dir html5lib

# Copy and install required packages
COPY requirements.txt .
RUN python3.10 -m pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3.10", "launch.py"]
