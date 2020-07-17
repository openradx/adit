import argparse
import configparser
import logging
from pathlib import Path
from datetime import datetime
from main.utils.anonymizer import Anonymizer
from main.utils.dicom_handler import DicomHandler
from batch_transfer.utils.excel_loader import ExcelLoader
from batch_transfer.utils.batch_handler import BatchHandler

class AditCmd:
    def __init__(self, config_ini_path, excel_file_path, worksheet=None):
        self.config = self._load_config_from_ini(config_ini_path)
        self._setup_logging()

        if self._check_file_already_open(excel_file_path):
            raise IOError('Excel file already in use by another program, please close.')

        self._excel_loader = ExcelLoader(excel_file_path, worksheet=worksheet)
        self._batch_handler = BatchHandler(self._create_batch_handler_config())

        self._results = []

    def _load_config_from_ini(self, config_ini_path):
        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(config_ini_path)
        return config['DEFAULT']

    def _setup_logging(self):
        log_level = logging.INFO
        if 'LogLevel' in self.config:
            if self.config['LogLevel'] == 'DEBUG':
                log_level = logging.DEBUG
            elif self.config['LogLevel'] == 'WARNING':
                log_level = logging.WARNING
            elif self.config['LogLevel'] == 'ERROR':
                log_level = logging.ERROR

        log_folder_path = Path('.')
        if 'LogFolder' in self.config:
            log_folder_path = Path(self.config['LogFolder'])
        log_filename = 'adit_log_' + datetime.now().strftime('%Y%m%d%H%M%S')
        log_path = log_folder_path / log_filename

        logging.basicConfig(
            level=log_level,
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

    def _create_batch_handler_config(self):
        return BatchHandler.Config(
            username=self.config['Username'],
            client_ae_title=self.config['ClientAETitle'],
            source_ae_title=self.config.get('SourceAETitle'),
            source_ip=self.config.get('SourceIP'),
            source_port=self.config.getint('SourcePort'),
            destination_ae_title=self.config.get('DestinationAETitle'),
            destination_ip=self.config.get('DestinationIP'),
            destination_port=self.config.getint('DestinationPort'),
            destination_folder=self.config.get('DestinationFolder'),
            trial_protocol_id=self.config.get('TrialProtocolID', ''),
            trial_protocol_name=self.config.get('TrialProtocolName', ''),
            pseudonymize=self.config.getboolean('Pseudonymize', True),
            cache_folder=self.config.get('CacheFolder', '/tmp'),
            batch_timeout=self.config.get('BatchTimeout', 0)
        )

    def _print_status(self, status):
        if status == DicomHandler.ERROR:
            print('E', end='', flush=True)
        else:
            print('.', end='', flush=True)

    def fetch_patient_ids(self):
        raise NotImplementedError # TODO

    def batch_download(self, archive_password=None):
        self._batch_handler.batch_download(
            self._excel_loader.extract_data(),
            lambda result: self._results.append(result),
            archive_password
        )
        print(self._results)

    def batch_transfer(self):
        self._batch_handler.batch_transfer(
            self._excel_loader.extract_data(),
            lambda result: self._results.append(result)
        )

    def close(self):
        self._excel_loader.close()


def password_type(password):
    print(password)
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
        parser.add_argument('-d', '--download', action='store_true',
                help='Download studies into the destination folder')
        parser.add_argument('-a', '--archive', action='store', type=password_type,
                help='Download studies into an archive that is encrypted with the provided password')
        parser.add_argument('-t', '--transfer', action='store_true',
                help='Transfer studies from the source PACS server to the destination server')
        return parser.parse_args()


if __name__ == '__main__':
    args = parse_cmd_args()
    adit_cmd = AditCmd(args.config_ini, args.excel_file, args.worksheet)

    if args.ids:
        adit_cmd.fetch_patient_ids()
    elif args.download:
        adit_cmd.batch_download()
    elif args.transfer:
        adit_cmd.batch_transfer()
