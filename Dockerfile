# @file       Dockerfile
# @brief      Dockerfile for PMFuzz
# @copyright  2021 PMFuzz Authors
# SPDX-license-identifier: BSD-3-Clause

# Only tested on Ubuntu 18.04, other versions *may* work
FROM ubuntu:18.04

# Install dependencies
RUN apt-get update
RUN apt-get install -y build-essential libunwind-dev libini-config-dev make git wget cmake
RUN apt-get install -y python3 python3-pip
RUN apt-get install -y man manpages-posix

# Clone PMFuzz
RUN git clone https://github.com/Systems-ShiftLab/pmfuzz.git
WORKDIR pmfuzz

# Install python dependencies
RUN pip3 install -r src/pmfuzz/requirements.txt

# Configure the system
RUN mkdir -p /usr/local/share/man/man1/
RUN mkdir -p /usr/local/share/man/man7/

# Build and install PMFuzz
RUN make
RUN make install
