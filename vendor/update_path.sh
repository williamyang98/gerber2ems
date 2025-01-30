#!/bin/env bash
SCRIPT_PATH=$(realpath $(dirname ${BASH_SOURCE[0]}))
export PATH=$PATH:$SCRIPT_PATH/gerbv/:$SCRIPT_PATH/openems/openEMS/
export OPENEMS_INSTALL_PATH=$SCRIPT_PATH/openems/openEMS/
