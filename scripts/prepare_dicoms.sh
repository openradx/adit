#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
CMD="$DIR/prepare_dicoms.py"

python $CMD ./input/apple_ct ./output -a -m PatientID "1001" -m PatientName "Apple^Annie" -m PatientBirthDate "19450427" -m PatientSex "F" -m StudyDate "20190604"
python $CMD ./input/coconut_mr ./output -a -m PatientID "1002" -m PatientName "Coconut^Coco" -m PatientBirthDate "19761209" -m PatientSex "F" -m StudyDate "20190601"
python $CMD ./input/grapefruit_mr ./output -a -m PatientID "1003" -m PatientName "Grapefruit^Graham" -m PatientBirthDate "19570123" -m PatientSex "M" -m StudyDate "20200202"
python $CMD ./input/mango_ct ./output -a -m PatientID "1004" -m PatientName "Mango^Mona" -m PatientBirthDate "19621204" -m PatientSex "F" -m StudyDate "20151227"
python $CMD ./input/papaya_ct ./output -a -m PatientID "1005" -m PatientName "Papaya^Pamela" -m PatientBirthDate "19760829" -m PatientSex "F" -m StudyDate "20180820"
python $CMD ./input/papaya_mr ./output -a -m PatientID "1005" -m PatientName "Papaya^Pamela" -m PatientBirthDate "19760829" -m PatientSex "F" -m StudyDate "20180819"
python $CMD ./input/pineapple_mr ./output -a -m PatientID "1006" -m PatientName "Pineapple^Peter" -m PatientBirthDate "19601102" -m PatientSex "M" -m StudyDate "20200529"
python $CMD ./input/starfruit_mr ./output -a -m PatientID "1007" -m PatientName "Starfruit^Stella" -m PatientBirthDate "19720607" -m PatientSex "F" -m StudyDate "20121115"
python $CMD ./input/watermelon_ct ./output -a -m PatientID "1008" -m PatientName "Watermelon^Willi" -m PatientBirthDate "19530331" -m PatientSex "M" -m StudyDate "20130105"
python $CMD ./input/watermelon_mr ./output -a -m PatientID "1008" -m PatientName "Watermelon^Willi" -m PatientBirthDate "19530331" -m PatientSex "M" -m StudyDate "20200705"