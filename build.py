import json
import requests
import os

try: os.system("rm -r version")
except: pass

def download(file_path, url):
    os.system(f"mkdir -p $(dirname {file_path})")
    os.system(f"wget {url} -O {file_path}")

VERSION_DIR = "version"
LIBRARIES_DIR = f"{VERSION_DIR}/libraries"
NATIVES_DIR = f"{LIBRARIES_DIR}/natives"

version = requests.get("https://piston-meta.mojang.com/v1/packages/924a2dcd8bdc31f8e9d36229811c298b3537bbc7/1.5.2.json").json()
download("{VERSION_DIR}/client.jar", version["downloads"]["client"]["url"])
for index, library in enumerate(version["libraries"]):
    try: download(f"{LIBRARIES_DIR}/{index}.jar", library["downloads"]["artifact"]["url"])
    except KeyError: pass

    try: download(f"{NATIVES_DIR}/{index}.jar", library["downloads"]["classifiers"]["natives-linux"]["url"])
    except KeyError: pass
    else: os.system(f"cd {NATIVES_DIR} && unzip {index}.jar && rm {index}.jar && rm -r META-INF")

os.system("mkdir {VERSION_DIR}/state")
