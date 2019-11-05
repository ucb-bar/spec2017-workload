SPEC2017 Workload
=================

Requirements
------------

- SPEC2017 installed and have `SPEC_DIR` env. variable point to installation

Getting Started
---------------

First install this repository into FireMarshal:

    cd /PATH/TO/FIREMARSHAL/firemarshal/example-workloads
    git submodule add https://github.com/ucb-bar/spec2017-workload.git spec2017

When you first install this repository, you should update all submodules:

    cd /PATH/TO/FIREMARSHAL/firemarshal/example-workloads
    git submodule update --init --recursive spec2017

After that you can use FireMarshal as normal and point to the `json` workload configs:

    # build
    cd /PATH/TO/FIREMARSHAL/firemarshal/example-workloads
    ./marshal build example-workloads/spec2017/marshal-configs/spec17-intrate.json
