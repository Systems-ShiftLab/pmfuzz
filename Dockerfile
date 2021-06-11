# @file       Dockerfile
# @brief      Dockerfile for PMFuzz
# @copyright  2021 PMFuzz Authors
# SPDX-license-identifier: BSD-3-Clause

# Only tested on Ubuntu 18.04, other versions *may* work
FROM ubuntu:18.04

# Install dependencies
RUN apt-get update
RUN apt-get install -y build-essential libunwind-dev libini-config-dev make git wget cmake

# Clone and build PMFuzz
RUN git clone https://github.com/Systems-ShiftLab/pmfuzz.git
WORKDIR pmfuzz
RUN make -j
