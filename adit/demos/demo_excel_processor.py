import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from pprint import pprint
from tools import ExcelProcessor # pylint: disable-msg=import-error

processor = ExcelProcessor('../samples/sample_sheet.xlsx')
processor.open('Normalized')

pprint(processor.data)