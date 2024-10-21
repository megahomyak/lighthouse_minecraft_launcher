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

os.system(f"rm -rf {version_id}")
os.system(f"mkdir {version_id}")
os.chdir(f"{version_id}")
os.system("mkdir libraries")
os.system("mkdir libraries/natives")
os.system("mkdir state")

def download_file(file_path, url):
    os.system(f"mkdir -p $(dirname {file_path})")
    os.system(f"wget {url} -O {file_path}")

library_paths = []

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

    try:
        artifact_url = library["downloads"]["artifact"]["url"]
    except KeyError:
        pass
    else:
        provided_artifact_path = library["downloads"]["artifact"]["path"]
        artifact_name = os.path.basename(provided_artifact_path)
        actual_artifact_path = f"libraries/{index}-{artifact_name}"
        download_file(actual_artifact_path, artifact_url)
        library_paths.append(actual_artifact_path)

    try:
        natives_url = library["downloads"]["classifiers"]["natives-linux"]["url"]
    except KeyError:
        pass
    else:
        download_file(f"libraries/natives/natives.jar", natives_url)
        os.system(f"cd libraries/natives && unzip -o natives.jar && rm natives.jar && rm -rf META-INF")

### Preparing the runner script

java_version = version["javaVersion"]["majorVersion"]

java_path = subprocess.run(["sh", "-c", f"update-alternatives --list java | grep java-{java_version}-"], capture_output=True).stdout.decode("utf-8").strip() or f"JAVA_{java_version}_NOT_FOUND"

class_path = ["client.jar"] + library_paths

with open("run.sh", "w") as f:
    f.write("#!/usr/bin/sh\n")
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
os.system("chmod +x run.sh")
