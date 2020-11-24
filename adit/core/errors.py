class NoSpaceLeftError(Exception):
    def __init__(self, path):
        super().__init__()
        self.path = path


class DownloadError(Exception):
    def __init__(self, message="", study_uid=None, series_uid=None, image_uids=None):
        super().__init__(message)
        self.study_uid = study_uid
        self.series_uid = series_uid
        self.image_uids = image_uids


class UploadError(Exception):
    def __init__(self, message="", image_uids=None):
        super().__init__(message)
        self.image_uids = image_uids
