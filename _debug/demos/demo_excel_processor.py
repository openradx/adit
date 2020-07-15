import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from pprint import pprint
from ..tools import ExcelLoader # pylint: disable-msg=import-error

loader = ExcelLoader('../samples/sample_sheet.xlsx')
loader.open('Normalized')

pprint(processor.data)