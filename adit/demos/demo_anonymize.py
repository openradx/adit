import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from tools import Anonymizer # pylint: disable-msg=import-error

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
