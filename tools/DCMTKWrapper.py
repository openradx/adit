import subprocess


class DCMTKWrapper:
    def __init__(self, calling_aet: str, calling_port: str):
        self.calling_aet = calling_aet
        self.calling_port = calling_port

    def _run_command(self, cmd_list):
        print(f"Running: {' '.join(cmd_list)}")
        process = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout for unified logging
            text=True,
        )

        # Print output line-by-line as it arrives
        for line in process.stdout:
            print(line, end="")

        process.wait()
        if process.returncode != 0:
            raise RuntimeError(f"Command failed with return code {process.returncode}")
        print()

    def _ensure_query_elements(self, query: dict) -> dict:
        default_elements = {
            "PatientName": "",
            "PatientID": "",
            "StudyInstanceUID": "",
            "StudyDate": "",
            "StudyDescription": "",
            "SeriesInstanceUID": "",
            "SeriesDescription": "",
            "SeriesDate": "",
            "Modality": "",
            "AccessionNumber": "",
        }

        for tag, default_value in default_elements.items():
            if tag not in query:
                query[tag] = default_value

        return query

    def _build_k_params(self, query: dict):
        k_args = []
        for key, value in query.items():
            k_args += ["-k", f"{key}={value}"]
        return k_args

    def findscu(self, called_aet: str, called_host: str, called_port: int, query: dict):
        cmd = [
            "findscu",
            "-v",
            "-P",
            "-aet",
            self.calling_aet,
            "-aec",
            called_aet,
            called_host,
            str(called_port),
        ]
        query = self._ensure_query_elements(query)
        cmd += self._build_k_params(query)
        return self._run_command(cmd)

    def movescu(
        self, called_aet: str, called_host: str, called_port: int, dest_aet: str, query: dict
    ):
        cmd = [
            "movescu",
            "-v",
            "-P",
            "-aet",
            self.calling_aet,
            "-aec",
            called_aet,
            "-aem",
            dest_aet,
            called_host,
            str(called_port),
        ]
        cmd += self._build_k_params(query)
        return self._run_command(cmd)

    def getscu(
        self, called_aet: str, called_host: str, called_port: int, query: dict, output_dir=None
    ):
        cmd = [
            "getscu",
            "-v",
            "-P",
            "-aet",
            self.calling_aet,
            "-aec",
            called_aet,
            called_host,
            str(called_port),
        ]
        if output_dir:
            cmd += ["-od", output_dir]
        cmd += self._build_k_params(query)
        return self._run_command(cmd)

    def storescu(self, dest_aet: str, dest_host: str, dest_port: int, dicom_files):
        if isinstance(dicom_files, str):
            dicom_files = [dicom_files]
        cmd = [
            "storescu",
            "-v",
            "-r",
            "-aet",
            self.calling_aet,
            "-aec",
            dest_aet,
            dest_host,
            str(dest_port),
        ] + dicom_files

        return self._run_command(cmd)
