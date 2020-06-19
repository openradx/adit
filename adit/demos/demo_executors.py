import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from pprint import pprint
from executors import Config as ExConfig, Executor # pylint: disable-msg=import-error

config = ExConfig(
    "Medihack",
    "W999999",
    "V:\\ext02\\THOR-SchlampKai\\CACHE",
    "192.168.0.1",
    104,
    "Syngo1",
    "192.168.0.2",
    104,
    "Syngo2",
    "V:\\ext02\\THOR-SchlampKai\\DICOM",
    trial_name="Example Trial",
    cleanup=False
)

executor = Executor(config)



data = [{'birth_date': '19990101',
    'patient_id': '12345467',
    'patient_name': 'Foo^Bar',
    'pseudonym': '',
    'row_id': 2,
    'study_dates': ['20190102', '20200123']}]

executor.transfer(data, ['DX'], False, True, lambda x: print(x['status']))
