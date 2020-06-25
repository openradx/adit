from openpyxl import Workbook
from faker import Faker
import os

ROW_COUNT = 10

wb = Workbook()
ws = wb.active
fake = Faker()

ws.append((
    'RowID',
    'PatientID',
    'PatientName',
    'PatientBirthDate',
    'StudyDate',
    'Modality',
    'Pseudonym'
))

for i in range(ROW_COUNT):
    row_id = i
    patient_id = fake.numerify(text="##########")
    patient_name = f'{fake.first_name()}, {fake.last_name()}'
    patient_birth_date = fake.date_of_birth(minimum_age=15).strftime("%d.%m.%Y")
    study_date = fake.date_between(start_date='-2y', end_date='today').strftime("%d.%m.%Y")
    modality = fake.random_element(elements=('CT', 'MR', 'DX'))
    pseudonym = ''

    row = (row_id, patient_id, patient_name, patient_birth_date,
            study_date, modality, pseudonym)
    
    ws.append(row)

parent_folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
samples_folder = os.path.join(parent_folder, '_samples')
filename = f'sample_sheet_generated_{ROW_COUNT}.xlsx'
sample_sheet_path = os.path.join(samples_folder, filename)

wb.save(sample_sheet_path)