import argparse
import configparser
import logging
import os, shutil
from functools import partial
from pprint import pprint
from datetime import datetime
from main.utils.anonymizer import Anonymizer
from main.utils.dicom_transferrer import DicomTransferrer
from batch_transfer.utils.excel_processor import ExcelProcessor
from batch_transfer.utils.batch_transferrer import BatchTransferrer

class AditCmd:
    def __init__(self, config_ini_path, excel_file_path, worksheet=None):
        self.config = self._load_config_from_ini(config_ini_path)
        self._setup_logging()

        if self._check_file_already_open(excel_file_path):
            raise IOError('Excel file already in use by another program, please close.')

        self._excel_processor = ExcelProcessor(excel_file_path, worksheet=worksheet)
        self._transferrer = BatchTransferrer(self._create_transferrer_config())

        self._results = []

    def _load_config_from_ini(self, config_ini_path):
        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(config_ini_path)
        return config['DEFAULT']

    def _setup_logging(self):
        level = logging.INFO
        if self.config['LogLevel'] == 'DEBUG':
            level = logging.DEBUG
        elif self.config['LogLevel'] == 'WARNING':
            level = logging.WARNING
        elif self.config['LogLevel'] == 'ERROR':
            level = logging.ERROR

        d = datetime.now().strftime('%Y%m%d%H%M%S')
        log_filename = 'log_' + d
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
            file = open(file_path, 'r+b')
            file.close()
        except IOError:
            already_open = True

        return already_open

    def _create_transferrer_config(self):
        return BatchTransferrer.Config(
            username=self.config['Username'],
            client_ae_title=self.config['ClientAETitle'],
            cache_folder=self.config['CacheFolder'],
            source_ae_title=self.config.get('SourceAETitle'),
            source_ip=self.config.get('SourceIP'),
            source_port=self.config.getint('SourcePort'),
            destination_ae_title=self.config.get('DestinationAETitle'),
            destination_ip=self.config.get('DestinationIP'),
            destination_port=self.config.getint('DestinationPort'),
            destination_folder=self.config.get('DestinationFolder'),
            archive_name=self.config.get('ArchiveName'),
            trial_protocol_id=self.config.get('TrialProtocolID', ''),
            trial_protocol_name=self.config.get('TrialProtocolName', ''),
            pseudonymize=self.config.getboolean('Pseudonymize', True)
        )

    def _print_status(self, status):
        if status == DicomTransferrer.ERROR:
            print('E', end='', flush=True)
        else:
            print('.', end='', flush=True)

    def fetch_patient_ids(self):
        raise NotImplementedError # TODO

    def download(self, archive_password):
        self._transferrer.batch_download(
            self._excel_processor.extract_data(),
            lambda result: self._results.append(result),
            archive_password
        )

    def transfer(self):
        self._transferrer.batch_transfer(
            self._excel_processor.extract_data(),
            lambda result: self._results.append(result)
        )

    def close(self):
        self._excel_processor.close()


def password_type(password):
    if not password or len(password) < 5:
        raise argparse.ArgumentTypeError('Provide a password with at least 8 characters.')
    return password

def parse_cmd_args():
        parser = argparse.ArgumentParser()
        parser.add_argument('config_ini', help='The configiguration INI file.')
        parser.add_argument('excel_file', help='The name or path of the Excel file to process')
        parser.add_argument('-w', '--worksheet', help='The name of the worksheet in the Excel file')
        parser.add_argument('-i', '--ids', action='store_true',
            help='Find Patient IDs (by using Patient Name and Patient Birth Date')
        parser.add_argument('-d', '--download', action='store', type=password_type,
            help='Download studies to an archive that is encrypted with the provided password')
        parser.add_argument('-t', '--transfer', action='store_true',
            help='Transfer studies from one PACS server to another server')
        return parser.parse_args()


if __name__ == '__main__':
    args = parse_cmd_args()

    adit = None
    try:
        adit = AditCmd(args.config_ini, args.excel_file, args.worksheet)

        if args.ids:
            adit.fetch_patient_ids()
        elif args.download:
            password = args.download
            adit.download(password)
    
    except Exception as ex:
        print('Error: ' + str(ex))

    finally:
        if adit:
            adit.close()
