# import csv

# def parse_requests(csv_file):
#     dialect = csv.Sniffer().sniff(csv_file.read(1024))
#     csv_file.seek(0)
#     reader = csv.reader(csv_file, dialect)
#     for row in reader:
#         print(row)