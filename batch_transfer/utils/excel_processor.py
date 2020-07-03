import re
from openpyxl import load_workbook
import datetime

class ExcelError(Exception):
    def __init__(self, message, errors):
        super().__init__(message)
        self.errors = errors


class ExcelProcessor:
    ROW_ID_COL = 'row_id_col'
    PATIENT_ID_COL = 'patient_id_col'
    PATIENT_NAME_COL = 'patient_name_col'
    PATIENT_BIRTH_DATE_COL = 'patient_birth_date_col'
    STUDY_DATE_COL = 'study_date_col'
    MODALITY_COL = 'modality_col'
    PSEUDONYM_COL = 'pseudonym_col'
    EXCLUDE_COL = 'exclude_col'
    STATUS_COL = 'status_col'

    def __init__(self, excel_file, worksheet=None, cmd_line_mode=False):
        self._worksheet = worksheet
        self._cmd_line_mode = cmd_line_mode
        self._excel_file = excel_file
        self.wb = None
        self.ws = None
        self._cols = []

        self._open()

    # Find a specific column in an Excel sheet (by a title in the header row)
    def _search_column(self, column_title):
        col = 1
        while True:
            value = self.ws.cell(column=col, row=1).value
            if not value:
                break
            elif value == column_title:
                return col

            col += 1

        return None

    def _scan_columns(self):
        cols = dict()
        cols[self.ROW_ID_COL] = self._search_column('RowID')
        cols[self.PATIENT_ID_COL] = self._search_column('PatientID')
        cols[self.PATIENT_NAME_COL] = self._search_column('PatientName')
        cols[self.PATIENT_BIRTH_DATE_COL] = self._search_column('PatientBirthDate')
        cols[self.STUDY_DATE_COL] = self._search_column('StudyDate')
        cols[self.MODALITY_COL] = self._search_column('Modality')
        cols[self.PSEUDONYM_COL] = self._search_column('Pseudonym')
        cols[self.EXCLUDE_COL] = self._search_column('Exclude')
        cols[self.STATUS_COL] = self._search_column('Status')

        self._check_columns(cols)

        self._cols = cols

    def _check_columns(self, cols):
        required_columns = [
            self.ROW_ID_COL,
            self.PATIENT_ID_COL,
            self.PATIENT_NAME_COL,
            self.PATIENT_BIRTH_DATE_COL,
            self.STUDY_DATE_COL, 
            self.MODALITY_COL,
            self.PSEUDONYM_COL
        ]

        if self._cmd_line_mode:
            required_columns.append(self.STATUS_COL)

        for column_name in required_columns:
            if not cols[column_name]:
                self._errors.append(f'{column_name} column missing')

    def _open(self):
        self._errors = []

        self.wb = load_workbook(filename=self._excel_file)

        if self._worksheet is not None:
            self.ws = self.wb[self._worksheet]
        else:
            self.ws = self.wb.active

        self._scan_columns()

        if len(self._errors) > 0:
            raise ExcelError(f'Invalid format of Excel file', self._errors)

    def _scan_rows(self):
        cols = self._cols

        r = 2 # Skip the header row
        while(True):
            row_id = self.ws.cell(column=cols[self.ROW_ID_COL], row=r).value
            patient_id = self.ws.cell(column=cols[self.PATIENT_ID_COL], row=r).value
            patient_name = self.ws.cell(column=cols[self.PATIENT_NAME_COL], row=r).value
            patient_birth_date = self.ws.cell(column=cols[self.PATIENT_BIRTH_DATE_COL], row=r).value
            modality = self.ws.cell(column=cols[self.MODALITY_COL], row=r).value
            study_date = self.ws.cell(column=cols[self.STUDY_DATE_COL], row=r).value
            pseudonym = self.ws.cell(column=cols[self.PSEUDONYM_COL], row=r).value

            # Check for an empty row and then stop parsing
            if not (row_id or patient_id or patient_name or patient_birth_date
                    or modality or study_date or pseudonym):
                break

            exclude = False
            if cols[self.EXCLUDE_COL]:
                exclude = bool(self.ws.cell(column=cols[self.EXCLUDE_COL], row=r).value)

            if not exclude:
                row = dict()
                row['RowID'] = self._clean_row_id(row_id, r)
                row['PatientID'] = self._clean_patient_id(patient_id)
                row['PatientName'] = self._clean_patient_name(patient_name)
                row['PatientBirthDate'] = self._clean_patient_birth_date(patient_birth_date, r)
                row['Modality'] = self._clean_modality(modality, r)
                row['StudyDate'] = self._clean_study_date(study_date, r)
                row['Pseudonym'] = self._clean_pseudonym(pseudonym)
                self._clean_row(row, r)

                self._data.append(row)

            r += 1

    def _clean_row_id(self, row_id, r):
        row_id = str(row_id).strip()
        if row_id and row_id not in self._row_ids:
            self._row_ids.add(row_id)
            return row_id
        elif row_id and row_id in self._row_ids:
            self._errors.append('Duplicate RowID in row ' % r)  
        else:
            self._errors.append('Missing RowID in Excel row ' % r)

    def _clean_patient_id(self, patient_id):
        patient_id = str(patient_id).strip()
        return str(patient_id) if patient_id else ''

    def _clean_patient_name(self, patient_name):
        return re.sub(r',\s*', '^', str(patient_name).strip()) if patient_name else ''

    def _clean_patient_birth_date(self, patient_birth_date, r):
        if patient_birth_date and isinstance(patient_birth_date, datetime.datetime):
            return patient_birth_date
        elif patient_birth_date:
            self._errors.append('Invalid PatientBirthDate (row %d)' % r)
        else:
            self._errors.append('Missing PatientBirthDate (row %d)' % r)

    def _clean_modality(self, modality, r):
        if modality:
            return str(modality)
        else:
            self._errors.append('Missing Modality (row %d)' % r)

    def _clean_study_date(self, study_date, r):
        if study_date and isinstance(study_date, datetime.datetime):
            return study_date
        elif study_date:
            self._errors.append('No valid StudyDate (row %d)' % r)
        else:
            self._errors.append('Missing StudyDate (row %d)' % r)

    def _clean_pseudonym(self, pseudonym):
        return str(pseudonym) if pseudonym else ''

    def _clean_row(self, row, r):
        if not(row['PatientID'] or (row['PatientName'] and row['PatientBirthDate'])):
            self._errors.append('Missing PatientID or PatientName/PatientBirthDate (row %d)' % r)

        # TODO check that combination patient_id and pseudonym is unique
        # TODO check that combination patient_name and patient_birth_date and pseudonym is unique
        # TODO check that combination patient_id and patient_name and patient_birth_date is unique

    def extract_data(self):
        self._row_ids = set()
        self._data = []
        self._errors = []

        self._scan_rows()

        if len(self._errors) > 0:
            raise ExcelError(f'Invalid format of Excel file', self._errors)

        return self._data

    def close(self):
        self.wb.close()

    def save(self):
        self.wb.save(filename=self._excel_file)

    def set_cell_value(self, column_name, row, value):
        column = self._cols[column_name]
        self.ws.cell(column=column, row=row, value=value)