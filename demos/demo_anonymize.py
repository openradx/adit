import sys
from pathlib import Path

path = Path(__file__).parent.parent.resolve()
sys.path.append(path.as_posix())

# pylint: disable-msg=wrong-import-position
from adit.main.utils.anonymizer import Anonymizer

anonymizer = Anonymizer()
# anonymizer.anonymize_folder(
# "V:\\ext02\\THOR-SchlampKai\\DICOM",
# "foobar",
# "Foo, Bar",
# callback=lambda ds: print(".", end="", flush=True))

for x in range(10):
    print(anonymizer.generate_pseudonym())
for x in range(10):
    print(anonymizer.generate_pseudonym(random_string=False))
