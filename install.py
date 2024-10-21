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

try: os.system(f"rm -r {version_id}")
except: pass
os.system(f"mkdir {version_id}")
os.chdir(f"{version_id}")
os.system("mkdir libraries")
os.system("mkdir libraries/natives")
os.system("mkdir state")

def download_file(file_path, url):
    os.system(f"mkdir -p $(dirname {file_path})")
    os.system(f"wget {url} -O {file_path}")

version = requests.get(version_url).json()
download_file("client.jar", version["downloads"]["client"]["url"])
for index, library in enumerate(version["libraries"]):
    if "rules" in library:
        allowed = False
        for rule in library["rules"]:
            if "os" in rule:
                if rule["os"]["name"] == "linux":
                    allowed = rule["action"] == "allow"
            else:
                allowed = rule["action"] == "allow"
        if not allowed:
            continue

    try: download_file(f"libraries/{index}.jar", library["downloads"]["artifact"]["url"])
    except KeyError: pass

    try: download_file(f"libraries/natives/{index}.jar", library["downloads"]["classifiers"]["natives-linux"]["url"])
    except KeyError: pass
    else: os.system(f"cd libraries/natives && unzip {index}.jar && rm {index}.jar && rm -r META-INF")

### Preparing the runner script

java_version = version["javaVersion"]["majorVersion"]

java_path = subprocess.run(["sh", "-c", f"update-alternatives --list java | grep java-{java_version}-"], capture_output=True).stdout.decode("utf-8").strip() or f"JAVA_{java_version}_NOT_FOUND"

class_path = ["client.jar"]
for file_name in os.listdir("libraries"):
    class_path.append(f"libraries/{file_name}")

with open("run.sh", "w") as f:
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
