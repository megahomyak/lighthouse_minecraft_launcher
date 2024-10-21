import json
import requests
import os
import sys
import subprocess
import shlex

### Downloading the version list

def download_json(url):
    return requests.get(url).json()

versions = download_json("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json")["versions"]

try:
    version_id = sys.argv[1]
except IndexError:
    for version in versions:
        print(f"{version['id']} - {version['type'].upper()}")
    exit()
else:
    for version in versions:
        if version["id"] == version_id:
            version_url = version["url"]
            break
    else:
        raise Exception(f"Can't find version {version_id}")

### Installing the version

try: os.system("rm -r version")
except: pass
os.system("mkdir version")
os.system("mkdir version/libraries")
os.system("mkdir version/libraries/natives")
os.system("mkdir version/state")

def download_file(file_path, url):
    os.system(f"mkdir -p $(dirname {file_path})")
    os.system(f"wget {url} -O {file_path}")

version = requests.get(version_url).json()
download_file("version/client.jar", version["downloads"]["client"]["url"])
for index, library in enumerate(version["libraries"]):
    try: download_file(f"version/libraries/{index}.jar", library["downloads"]["artifact"]["url"])
    except KeyError: pass

    try: download_file(f"version/libraries/natives/{index}.jar", library["downloads"]["classifiers"]["natives-linux"]["url"])
    except KeyError: pass
    else: os.system(f"cd version/libraries/natives && unzip {index}.jar && rm {index}.jar && rm -r META-INF")

### Preparing the runner script

java_version = version["javaVersion"]["majorVersion"]

java_path = subprocess.run(["sh", "-c", f"update-alternatives --list java | grep java-{java_version}-"], capture_output=True).stdout.decode("utf-8").strip() or f"JAVA_{java_version}_NOT_FOUND"

class_path = ["client.jar"]
for file_name in os.listdir("version/libraries"):
    class_path.append(f"libraries/{file_name}")

with open("version/run.sh", "w") as f:
    f.write(" ".join([
        shlex.quote(argument)
        for argument in [
            java_path,
            "-cp",
            ":".join(class_path),
            "-Djava.library.path=libraries/natives",
            version["mainClass"],
            "--gameDir",
            "state",
        ]
    ]))
