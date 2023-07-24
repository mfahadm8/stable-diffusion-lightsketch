FROM pytorch/pytorch:1.11.0-cuda11.3-cudnn8-runtime

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


RUN apt-get install  -y  python3-wheel
RUN python -m pip install wheel

RUN python -m pip install pyyaml==5.1

WORKDIR /app

COPY . .

CMD ["python3.10", "launch.py"]
