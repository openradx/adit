import subprocess


class DCMTKWrapper:
    """
    A wrapper class for DCMTK command-line tools to perform DICOM network operations
    such as C-FIND, C-MOVE, C-GET, and C-STORE with configurable AE titles and ports.
    """

    def __init__(self, calling_aet: str, calling_port: str):
        """
        Initiates the class with the AE title of the calling node and its port (currently not needed since there is no C-STORE SCP implementation.)

        Args:
            calling_aet (str): AE title of the calling DICOM node.
            calling_port (int): Port number of the calling node.

        Returns:
            DCMTKWrapper object: The object itself.
        """
        self.calling_aet = calling_aet
        self.calling_port = calling_port

    def _run_command(self, cmd_list, print_output) -> int:
        """
        Executes a command-line process and optionally prints its output.

        Args:
            cmd_list (list): List of command and arguments to execute.
            print_output (bool): Whether to print the command output.

        Returns:
            int: The return code of the executed command.
        """
        if print_output:
            print(f"Running: {' '.join(cmd_list)}")
        process = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout for unified logging
            text=True,
        )

        # Print output line-by-line as it arrives
        if process.stdout is not None and print_output:
            for line in process.stdout:
                print(line, end="")
            print("#########################################") # Delimiter for better readability
        process.wait()
        return process.returncode

    def _ensure_query_elements(self, query: dict) -> dict:
        """
        Ensures that a query dictionary contains all required DICOM query elements,
        adding default empty values for missing elements.

        Args:
            query (dict): The original query dictionary.

        Returns:
            dict: The query dictionary with all required elements ensured.
        """
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

    def _build_k_params(self, query: dict) -> list[str]:
        """
        Builds a list of '-k' parameters for DCMTK commands from a query dictionary.

        Args:
            query (dict): Dictionary of DICOM query key-value pairs.

        Returns:
            list[str]: List of parameters formatted as ['-k', 'key=value', ...].
        """
        k_args = []
        for key, value in query.items():
            k_args += ["-k", f"{key}={value}"]
        return k_args

    def findscu(
        self,
        called_aet: str,
        called_host: str,
        called_port: int,
        query: dict,
        print_output=True,
    ) -> int:
        """
        Performs a C-FIND operation to query a remote DICOM AE for matching datasets.

        Args:
            called_aet (str): AE title of the called DICOM node.
            called_host (str): Hostname or IP address of the called node.
            called_port (int): Port number of the called node.
            query (dict): Dictionary of DICOM query elements.
            print_output (bool, optional): Whether to print command output. Defaults to True.

        Returns:
            int: Return code of the findscu command execution.
        """
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
        return self._run_command(cmd, print_output)

    def movescu(
        self,
        called_aet: str,
        called_host: str,
        called_port: int,
        dest_aet: str,
        query: dict,
        print_output=True,
    ) -> int:
        """
        Performs a C-MOVE operation to retrieve DICOM datasets from a remote AE and send them to a destination AE.

        Args:
            called_aet (str): AE title of the called DICOM node.
            called_host (str): Hostname or IP address of the called node.
            called_port (int): Port number of the called node.
            dest_aet (str): AE title of the destination node to receive the datasets.
            query (dict): Dictionary of DICOM query elements.
            print_output (bool, optional): Whether to print command output. Defaults to True.

        Returns:
            int: Return code of the movescu command execution.
        """
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
        return self._run_command(cmd, print_output)

    def getscu(
        self,
        called_aet: str,
        called_host: str,
        called_port: int,
        query: dict,
        output_dir=None,
        print_output=True,
    ) -> int:
        """
        Performs a C-GET operation to retrieve DICOM datasets from a remote AE and store them locally.

        Args:
            called_aet (str): AE title of the called DICOM node.
            called_host (str): Hostname or IP address of the called node.
            called_port (int): Port number of the called node.
            query (dict): Dictionary of DICOM query elements.
            output_dir (str, optional): Directory to store received files. Defaults to None.
            print_output (bool, optional): Whether to print command output. Defaults to True.

        Returns:
            int: Return code of the getscu command execution.
        """
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
        return self._run_command(cmd, print_output)

    def storescu(
        self,
        dest_aet: str,
        dest_host: str,
        dest_port: int,
        dicom_files: str | list[str],
        print_output=True,
    ) -> int:
        """
        Performs a C-STORE SCU operation to send DICOM files to a remote AE.

        Args:
            dest_aet (str): AE title of the destination DICOM node.
            dest_host (str): Hostname or IP address of the destination node.
            dest_port (int): Port number of the destination node.
            dicom_files (str or list[str]): Path(s) to DICOM file(s) to send.
            print_output (bool, optional): Whether to print command output. Defaults to True.

        Returns:
            int: Return code of the storescu command execution.
        """
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
        return self._run_command(cmd, print_output)
