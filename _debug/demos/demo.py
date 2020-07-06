import sys, os
root_folder = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.append(root_folder)

from batch_transfer.utils.batch_transferrer import BatchTransferrer, BatchTransferrerConfig

tmp_folder = os.path.join(root_folder, '_tmp')

config = BatchTransferrerConfig(
    'kai',
    'ADIT',
    tmp_folder,
    'OTRTHANC1',
    '127.0.0.1',
    7501
)

transferrer = BatchTransferrer(config)

from datetime import datetime
result = transferrer.find_patients('patient1', '', '')
result = transferrer.find_studies('patient1', datetime(2008, 7, 23))
study_uid = '1.2.840.113619.2.176.3596.10293044.8073.1216822352.891'
result = transferrer.find_series('patient1', study_uid, ['MR'])

series_uid = '1.2.840.113619.2.176.3596.10293044.8073.1216822352.894'
#transferrer.download_series('patient1', study_uid, series_uid, tmp_folder)
#transferrer.download_study('patient1', study_uid, tmp_folder, create_series_folders=False)
transferrer.download_patient('patient1', tmp_folder)
