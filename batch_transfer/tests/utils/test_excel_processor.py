from django.test import TestCase
from django.conf import settings
import os
from batch_transfer.utils.excel_processor import ExcelProcessor

class ExcelProcessorTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        excel_file_path = os.path.join(settings.BASE_DIR, 
                '_samples', 'sample_sheet_valid_small.xlsx')
        cls.excel_file = open(excel_file_path, 'rb')
        
    def test_open_valid_excel_batch_file(self):
        processor = ExcelProcessor(self.excel_file)
        data = processor.extract_data()
        self.assertEquals(len(data), 3)
        self.assertEquals(data[0]['PatientName'], 'Turner^Yolanda')
        self.assertEquals(data[0]['Modality'], 'MR')
        self.assertEquals(data[1]['PatientID'], '9918223726')
        self.assertEquals(data[1]['RowID'], '2')
        self.assertEquals(data[1]['StudyDate'], '20181219')
        self.assertEquals(data[2]['PatientBirthDate'], '19461211')
        self.assertEquals(data[2]['Pseudonym'], 'AXPVQR47')
