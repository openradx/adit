from adit.core.utils.batch_parsers import BatchFileParser
from ..serializers import BatchQueryTaskSerializer


class BatchQueryFileParser(BatchFileParser):
    serializer_class = BatchQueryTaskSerializer
