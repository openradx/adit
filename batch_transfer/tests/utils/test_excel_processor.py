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
        processor.open()
        data = processor.data
        print(data)
        self.assertEquals(len(data), 3)
        self.assertEquals(data[1]['RowID'], '2')