#!/usr/bin/env bash

docker run --rm -v adit_dev_syslog_data:/mnt/adit_logs -w /mnt/adit_logs -it ubuntu /bin/bash
