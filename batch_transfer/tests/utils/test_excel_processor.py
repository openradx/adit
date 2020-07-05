from django.test import TestCase
from django.conf import settings
import os
from datetime import datetime
from batch_transfer.utils.excel_processor import ExcelProcessor

class ExcelProcessorTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        excel_file_path = os.path.join(settings.BASE_DIR, '_debug',
                'samples', 'sample_sheet_valid_small.xlsx')
        cls.excel_file = open(excel_file_path, 'rb')
        
    def test_open_valid_excel_batch_file(self):
        processor = ExcelProcessor(self.excel_file)
        data = processor.extract_data()
        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]['PatientName'], 'Turner^Yolanda')
        self.assertEqual(data[0]['Modality'], 'MR')
        self.assertEqual(data[1]['PatientID'], '9918223726')
        self.assertEqual(data[1]['RequestID'], '2')
        study_date = datetime(2018, 12, 19)
        self.assertEqual(data[1]['StudyDate'], study_date)
        patient_birth_date = datetime(1946, 12, 11)
        self.assertEqual(data[2]['PatientBirthDate'], patient_birth_date)
        self.assertEqual(data[2]['Pseudonym'], 'AXPVQR47')
