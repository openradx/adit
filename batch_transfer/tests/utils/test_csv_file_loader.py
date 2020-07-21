# from django.test import TestCase
# from django.conf import settings
# from pathlib import Path
# from datetime import datetime
# from ...utils.csv_file_loader import parse_requests

# class CsvFileLoaderTest(TestCase):
#     @classmethod
#     def setUpTestrequests(cls):
#         csv_file_path = (Path(settings.BASE_DIR) / '_debug' / 
#                 'samples' / 'sample_sheet_small.csv')
#         cls.csv_file = open(csv_file_path, 'rb')

#     def test_open_valid_excel_batch_file(self):
#         requests = parse_requests(self.excel_file)
#         self.assertEqual(len(requests), 3)
#         self.assertEqual(requests[0]['PatientName'], 'Papaya^Pamela')
#         self.assertEqual(requests[0]['Modality'], 'MR')
#         self.assertEqual(requests[1]['PatientID'], '10002')
#         self.assertEqual(requests[1]['RequestID'], '2')
#         study_date = datetime(2018, 3, 27)
#         self.assertEqual(requests[1]['StudyDate'], study_date)
#         patient_birth_date = datetime(1962, 2, 18)
#         self.assertEqual(requests[2]['PatientBirthDate'], patient_birth_date)
#         self.assertEqual(requests[2]['Pseudonym'], 'DEDH6SVQ')