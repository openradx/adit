from django.test import TestCase
from django.conf import settings
from pathlib import Path
from datetime import datetime
from batch_transfer.utils.excel_loader import ExcelLoader

class ExcelLoaderTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        excel_file_path = (Path(settings.BASE_DIR) / '_debug' / 
                'samples' / 'sample_sheet_small.xlsx')
        cls.excel_file = open(excel_file_path, 'rb')
        
    def test_open_valid_excel_batch_file(self):
        processor = ExcelLoader(self.excel_file)
        data = processor.extract_data()
        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]['PatientName'], 'Papaya^Pamela')
        self.assertEqual(data[0]['Modality'], 'MR')
        self.assertEqual(data[1]['PatientID'], '10002')
        self.assertEqual(data[1]['RequestID'], '2')
        study_date = datetime(2018, 3, 27)
        self.assertEqual(data[1]['StudyDate'], study_date)
        patient_birth_date = datetime(1962, 2, 18)
        self.assertEqual(data[2]['PatientBirthDate'], patient_birth_date)
        self.assertEqual(data[2]['Pseudonym'], 'DEDH6SVQ')
