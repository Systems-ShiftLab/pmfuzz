#!/usr/bin/env bash

NDCTL_DIR=$1
SUDO="sudo"
sudo 2>/dev/null || SUDO=""

function clone_ndctl {
	git clone https://github.com/pmem/ndctl/ /tmp/ndctl-tmp-pmfuzz
	NDCTL_DIR=/tmp/ndctl-tmp-pmfuzz
	${BASH} -c "cd $NDCTL_DIR; git checkout v68;"
}

if [ "$#" -ne 1 ]; then
	echo 'No ndctl path specified, cloning from github'
	clone_ndctl
fi

$SUDO apt-get -y purge 'libdaxctl*' 'libndctl*'

$SUDO apt-get install autoconf bash-completion asciidoctor libkmod-dev libudev-dev uuid-dev libjson-c-dev libkeyutils-dev


pushd $NDCTL_DIR

$SUDO ./autogen.sh
$SUDO ./configure CFLAGS='-g -O2' --prefix=/usr/local --sysconfdir=/etc --libdir=/usr/local/lib64

popd

make -j40 -C "$NDCTL_DIR"
$SUDO make install -j40 -C "$NDCTL_DIR"
