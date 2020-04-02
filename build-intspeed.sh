#!/bin/bash

set -ex

if [ "$1" != "ref" ] && [ "$1" != "test" ] && [ "$1" != "train" ]; then
    echo "Must specify ref/test/train"
    exit 1
fi

echo "Building SPEC2017 Intspeed with $1 inputs"
make spec17-intspeed INPUT=$1
