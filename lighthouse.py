from subprocess import CalledProcessError as RunFailure
import os
join = os.path.join

def get_client_path(installation_directory):
    return join(installation_directory, "client.jar")

def get_libraries_directory_path(installation_directory):
    return join(installation_directory, "libraries")

def get_native_libraries_directory_path(libraries_directory):
    return join(libraries_directory, "natives")

def run(*args):
    import subprocess
    subprocess.run(args).check_returncode()

def install(game_info_url, installation_directory):
    import shutil
    import requests
    import urllib

    shutil.rmtree("version", ignore_errors=True)

    def download(file_path, url):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        urllib.request.urlretrieve(url, file_path)

    version = requests.get(game_info_url).json()
    download(get_client_path(installation_directory), version["downloads"]["client"]["url"])

    download(join(libraries_dir), )

def main():
    import argparse
    pass

main()
