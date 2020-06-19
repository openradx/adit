import argparse
import configparser
import logging
import os, shutil
from functools import partial
from pprint import pprint
from datetime import datetime
from tools import ExcelProcessor, Anonymizer
from dicom_conductor import DicomConductor, Config as ConConfig

class Adit:
    def __init__(self, config_ini_path, excel_file_path, worksheet_name):
        self.config = self._load_config_from_ini(config_ini_path)
        self._setup_logging()

        if self._check_file_already_open(excel_file_path):
            raise IOError("Excel file already in use by another program, please close.")

        self._excel_processor = ExcelProcessor(excel_file_path)
        self._excel_processor.open(worksheet_name)
        self._conductor = DicomConductor(self._create_conductor_config())

    def _load_config_from_ini(self, config_ini_path):
        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(config_ini_path)
        return config["DEFAULT"]

    def _setup_logging(self):
        level = logging.INFO
        if self.config['LogLevel'] == 'DEBUG':
            level = logging.DEBUG
        elif self.config['LogLevel'] == 'WARNING':
            level = logging.WARNING
        elif self.config['LogLevel'] == 'ERROR':
            level = logging.ERROR

        d = datetime.now().strftime("%Y%m%d%H%M%S")
        log_filename = "log_" + d
        log_path = os.path.join(self.config['LogFolder'], log_filename)

        logging.basicConfig(
            level=level,
            format='%(asctime)s %(levelname)-8s %(message)s',
            datefmt='%m-%d %H:%M',
            filename=log_path,
            filemode='a'
        )

    def _check_file_already_open(self, file_path):
        already_open = False
        try:
            file = open(file_path, "r+b")
            file.close()
        except IOError:
            already_open = True

        return already_open

    def _create_conductor_config(self):
        return ConConfig(
            username=self.config['Username'],
            client_ae_title=self.config['ClientAETitle'],
            cache_folder=self.config['CacheFolder'],
            source_ip=self.config.get('SourceIP'),
            source_port=self.config.getint('SourcePort'),
            source_ae_title=self.config.get('SourceAETitle'),
            target_ip=self.config.get('TargetIP'),
            target_port=self.config.getint('TargetPort'),
            target_ae_title=self.config.get('TargetAETitle'),
            archive_folder=self.config.get('ArchiveFolder'),
            archive_name=self.config.get('ArchiveName'),
            trial_name=self.config.get('TrialName', ""),
            pseudonymize=self.config.getboolean('Pseudonymize', True)
        )

    def _print_status(self, status):
        if status == DicomConductor.ERROR:
            print("E", end="", flush=True)
        else:
            print(".", end="", flush=True)

    def _process_result(self, column, result):
        self._print_status(result['Status'])
        if result['Status'] == DicomConductor.SUCCESS:
            self._excel_processor.set_cell_value(
                ExcelProcessor.STATUS_COL,
                result['RowID'],
                "Ok"
            )
            self._excel_processor.set_cell_value(
                column,
                result['RowID'],
                result['Message']
            )
        elif result['Status'] == DicomConductor.ERROR:
            self._excel_processor.set_cell_value(
                ExcelProcessor.STATUS_COL,
                result['RowID'],
                f"Error: {result['Message']}"
            )
        self._excel_processor.save()

    def fetch_patient_ids(self):
        callback = partial(self._process_result, ExcelProcessor.PATIENT_ID_COL)
        self._conductor.fetch_patient_ids(
            self._excel_processor.data,
            result_callback=callback
        )

    def download(self, archive_password):
        callback = partial(self._process_result, ExcelProcessor.PSEUDONYM_COL)
        self._conductor.download(
            self._excel_processor.data,
            archive_password,
            result_callback=callback
        )

    def transfer(self):
        callback = partial(self._process_result, ExcelProcessor.PSEUDONYM_COL)
        self._conductor.transfer(
            self._excel_processor.data,
            result_callback=callback
        )

    def close(self):
        self._excel_processor.close()


def password_type(password):
    if not password or len(password) < 5:
        raise argparse.ArgumentTypeError("Provide a password with at least 8 characters.")
    return password

def parse_cmd_args():
        parser = argparse.ArgumentParser()
        parser.add_argument("config_ini", help="The configiguration INI file.")
        parser.add_argument("excel_filename", help="The name or path of the Excel file to process")
        parser.add_argument("worksheet_name", help="The name of the worksheet in the Excel file")
        parser.add_argument("-i", "--ids", action="store_true",
            help="Find Patient IDs (by using Patient Name and Patient Birth Date")
        parser.add_argument("-d", "--download", action="store", type=password_type,
            help="Download studies to an archive that is encrypted with the provided password")
        parser.add_argument("-t", "--transfer", action="store_true",
            help="Transfer studies from one PACS server to another server")
        return parser.parse_args()


if __name__ == "__main__":
    args = parse_cmd_args()

    adit = None
    try:
        adit = Adit(args.config_ini, args.excel_filename, args.worksheet_name)

        if args.ids:
            adit.fetch_patient_ids()
        elif args.download:
            password = args.download
            adit.download(password)
    
    except Exception as ex:
        print("Error: " + str(ex))

    finally:
        if adit:
            adit.close()
