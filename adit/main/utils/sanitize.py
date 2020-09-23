import re


def sanitize_dirname(dirname):
    dirname = dirname.strip()
    dirname = re.sub(r"(\<|\>|\:|\"|\/|\\|\||\?|\*)", "", dirname)
    dirname = re.sub(r"(\.+)$", "", dirname)
    return dirname


def sanitize_filename(filename):
    return sanitize_dirname(filename)
