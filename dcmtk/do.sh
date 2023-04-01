#!/usr/bin/env bash

rm -rf ./build/
sudo apt-get -y install libsndfile1-dev libwrap0-dev libopenjp2-7-dev doxygen
export DCMDICTPATH=/workspace/dcmtk-3.6.7-install/usr/local/share/dcmtk/dicom.dic
cmake -S. -Bbuild -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build --target all
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/workspace/dcmtk-3.6.7-install/usr/local/lib/
./build/demo
