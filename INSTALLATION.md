Clone the repository to your desired location.

# Prerequisites
Linux distro, recommended latest Ubuntu
Install docker and docker compose. Recommended way: https://docs.docker.com/compose/install/standalone/
Install python 3.12. Recommended way: via your package manager: e.g sudo apt install python3.12
Install poetry: sudo pip3.12 install poetry

# Install ADIT
git clone https://github.com/openradx/adit.git
git config --global --add safe.directory full_path_to/adit
sudo chgrp docker -R adit
sudo chmod o-rwx -R adit
sudo chmod 770 adit
sudo chmod g+s adit
sudo chmod u+s adit

# Setup production ADIT
cd adit
poetry install
poetry shell
invoke init-workspace # Adjust env

# Start ADIT
cd adit
poetry shell
invoke compose-up

