from adit.continuous_transfer.models import ContinuousTransferJob


class QueryHelper:
    def __init__(self, job: ContinuousTransferJob):
        self.job = job
