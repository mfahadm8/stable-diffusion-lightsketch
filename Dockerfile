FROM nvidia/cuda:11.1.1-cudnn8-devel-ubuntu18.04
# use an older system (18.04) to avoid opencv incompatibility (issue#3524)
RUN apt-get install gcc
ENV DEBIAN_FRONTEND noninteractive
# # RUN apt-get update
# # RUN apt-get install -y software-properties-common
# # RUN add-apt-repository ppa:deadsnakes/ppa -y
# # RUN apt-get install -y python3.8

# # RUN apt-get install -y python3-pip

RUN apt-get update -qq   && apt-get install -y -qq python3.8
RUN apt-get install -y python3-pip python-dev python3.8-dev && python3 -m pip install pip --upgrade
# RUN rm /usr/bin/python && rm /usr/bin/python3 && ln -s /usr/bin/python3.8 /usr/bin/python &&  ln -s /usr/bin/python3.8 /usr/bin/python3 \
#     && rm /usr/local/bin/python && rm /usr/local/bin/python3 && ln -s /usr/bin/python3.8 /usr/local/bin/python &&  ln -s /usr/bin/python3.8 /usr/local/bin/python3 \
#     && apt-get install -y python3-pip python-dev python3.8-dev && python3 -m pip install pip --upgrade
    
    
    
    
 
 RUN : \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        software-properties-common \
    && add-apt-repository -y ppa:deadsnakes \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3.8-venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && :
RUN ln -s /usr/bin/python3.8 /usr/local/bin/python &&  ln -s /usr/bin/python3.8 /usr/local/bin/python3 


RUN apt-get update && apt-get install -y \
	python3-opencv ca-certificates python3-dev git wget sudo ninja-build
# # RUN ln -sv /usr/bin/python3 /usr/bin/python
# # RUN ln -s /usr/bin/python3.8 /usr/bin/python
# RUN ln -s /usr/bin/pip3 /usr/bin/pip && \
#     ln -s /usr/bin/python3.8 /usr/bin/python

# create a non-root user
# ARG USER_ID=1000
# RUN useradd -m --no-log-init --system  --uid ${USER_ID} appuser -g sudo
# RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
# USER appuser
# WORKDIR /home/appuser

# ENV PATH="/home/appuser/.local/bin:${PATH}"
# RUN wget https://bootstrap.pypa.io/pip/3.8/get-pip.py && \
# 	python get-pip.py --user && \
# 	rm get-pip.py



# install dependencies
# See https://pytorch.org/ for other options if you use a different version of CUDA
# RUN pip install --user tensorboard cmake onnx   # cmake from apt-get is too old
RUN apt-get install  -y  python3-wheel
RUN python -m pip install wheel

RUN python -m pip install pyyaml==5.1
# install detectron2
RUN git clone https://github.com/facebookresearch/detectron2 detectron2_repo

# set FORCE_CUDA because during `docker build` cuda is not accessible
ENV FORCE_CUDA="1"
# This will by default build detectron2 for all common cuda architectures and take a lot more time,
# because inside `docker build`, there is no way to tell which architecture will be used.
ARG TORCH_CUDA_ARCH_LIST="Kepler;Kepler+Tesla;Maxwell;Maxwell+Tegra;Pascal;Volta;Turing"
ENV TORCH_CU

WORKDIR /app

COPY . .

CMD ["python3.10", "launch.py"]
