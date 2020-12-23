from ubuntu:16.04

RUN sh -c 'echo "deb http://packages.ros.org/ros/ubuntu xenial main" > /etc/apt/sources.list.d/ros-latest.list'
RUN apt-key adv --keyserver 'hkp://keyserver.ubuntu.com:80' --recv-key C1CF6E31E6BADE8868B172B4F42ED6FBAB17C654
RUN apt update
RUN apt install -y ros-kinetic-ros-base --allow-unauthenticated
RUN echo ". /opt/ros/kinetic/setup.bash" >> ~/.bashrc

RUN apt install -y \
   wget \
   ros-kinetic-cv-bridge \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
RUN cd /tmp && wget https://bootstrap.pypa.io/get-pip.py && python get-pip.py

ENV WORKDIR /app/
WORKDIR ${WORKDIR}

COPY requirements.txt ${WORKDIR}
RUN pip install -r requirements.txt

COPY . ${WORKDIR}

SHELL ["/bin/bash", "-c"]
ENTRYPOINT ["/app/bin/docker-entrypoint.bash"]
CMD ["python libs/rosbag_extractor.py --help"]
