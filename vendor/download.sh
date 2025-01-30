#!/bin/sh

GERBV_URL="https://github.com/gerbv/gerbv/releases/download/v2.10.0/gerbv_2.10.0_037b94_Windows_amd64.zip"
GERBV_SHA256="a8be9ea85847d1b270e1aeb91a3f7db6a1d9f6f38f3452b175d6b51c0ac5ca51"
OPENEMS_URL="https://github.com/thliebig/openEMS-Project/releases/download/v0.0.36/openEMS_v0.0.36.zip"
OPENEMS_SHA256="e0d62b1176c0897ad18876b45667de877d7d3b58b37c0be95545f9b988896059"

SCRIPT_PATH=$(realpath $(dirname $0))

cd $SCRIPT_PATH

echo "Removing old vendor folders"
rm -rf ./gerbv
rm -rf ./openems

echo "Downloading vendor zips"
if ! test -f ./gerbv.zip; then
    curl -fLo ./gerbv.zip $GERBV_URL &
fi
if ! test -f ./openems.zip; then
    curl -fLo ./openems.zip $OPENEMS_URL &
fi
wait

# Verify hash
echo "Verifying zip hashes"
set -e
echo $GERBV_SHA256 gerbv.zip | sha256sum --check
echo $OPENEMS_SHA256 openems.zip | sha256sum --check

# Unzip
echo "Extracting vendor zips"
7z x ./gerbv.zip -ogerbv -y &
7z x ./openems.zip -oopenems -y &

wait

echo "Cleaning up vendor zips"
rm ./gerbv.zip
rm ./openems.zip

echo "Installed vendor folders"
