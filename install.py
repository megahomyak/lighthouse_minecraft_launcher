import json
import requests
import os
import sys
import urllib
import zipfile
import platform
import subprocess
import stat
import shutil
import pathlib
import hashlib

LIGHTHOUSE_VERSION_ID = "megahomyak-1"
LIGHTHOUSE_CONFIG_NAME = "lighthouse.config.json"

# Stolen from portablemc
current_os_name = {
    "Linux": "linux", 
    "Windows": "windows", 
    "Darwin": "osx",
}[platform.system()]

# Stolen from portablemc
processor_architecture = {
    "i386": "x86",
    "i686": "x86",
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "arm64": "arm64",
    "aarch64": "arm64",
    "armv7l": "arm32",
    "armv6l": "arm32",
}[platform.machine().lower()]

# Stolen from portablemc
minecraft_jvm_os = {
    "osx": {"x86_64": "mac-os", "arm64": "mac-os-arm64"},
    "linux": {"x86": "linux-i386", "x86_64": "linux"},
    "windows": {"x86": "windows-x86", "x86_64": "windows-x64", "arm64": "windows-arm64"},
}[current_os_name][processor_architecture]

### Downloading the version list

def download_json(url):
    return requests.get(url).json()

def get_versions_list():
    #####
    print("Getting the versions list")
    return download_json("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json")

def make_executable(file_path):
    st = os.stat(file_path)
    os.chmod(file_path, st.st_mode | stat.S_IEXEC)

def main():
    action = sys.argv[1]
    if action == "list":
        list_()
    elif action == "ensure":
        version_id = sys.argv[2]
        ensure(version_id)
    elif action == "run":
        version_id = sys.argv[2]
        run(version_id)
    else:
        raise Exception(f"Invalid action name \"{action}\"")

def get_sha1(path):
    with open(path, "rb") as f:
        return hashlib.sha1(f.read())

def download(url, path, expected_sha1_in_hex):
    print(f"Checking {path}... ", end="", flush=True)
    try:
        assert get_sha1(path).hexdigest() == expected_sha1_in_hex
    except:
        print("DOWNLOADING")
        urllib.request.urlretrieve(url, path)
    else:
        print("EXISTS")

def list_():
    versions_list = get_versions_list()
    print("LATEST:")
    print("* Release: " + versions_list["latest"]["release"])
    print("* Snapshot: " + versions_list["latest"]["snapshot"])
    print()
    for version in versions_list["versions"]:
        print(f"{version['id']} - {version['type'].upper()}")

def run(version_id):
    os.chdir(version_id)
    with open(LIGHTHOUSE_CONFIG_NAME, "r") as f:
        config = json.load(f)
    config_lighthouse_version_id = config["lighthouse_version_id"]
    if config_lighthouse_version_id == LIGHTHOUSE_VERSION_ID:
        arguments = config["run_arguments"]
        java_binary_path = config["java_binary_path"]
        print(f"Starting up {version_id} in a detached process")
        subprocess.Popen([java_binary_path, *arguments], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        raise Exception(f"Bad config version: expected {LIGHTHOUSE_VERSION_ID}, got {config_lighthouse_version_id}")

def ensure(version_id):
    versions_list = get_versions_list()["versions"]
    for version in versions_list:
        if version["id"] == version_id:
            version_url = version["url"]
            break
    else:
        raise Exception(f"Can't find version {version_id}")

    #####
    print("Writing the Lighthouse warning file")

    with open("WARNING_READ_ME.txt", "w") as f:
        f.write("This directory is used for the Lighthouse Minecraft launcher. Please, only modify the state of Minecraft version instances. Every other modification may break Lighthouse operations.")

    #####
    print("Getting the version JSON")

    version = requests.get(version_url).json()

    #####
    print("Checking the runtime")

    java_runtime_name = version["javaVersion"]["component"]
    java_runtime_path = os.path.join("runtimes", java_runtime_name)
    os.makedirs(java_runtime_path, exist_ok=True)
    #####
    print("Getting the runtimes list")

    runtimes = requests.get("https://launchermeta.mojang.com/v1/products/java-runtime/2ec0cc96c44e5a76b9c8b7c39df7210883d12871/all.json").json()
    files_url = runtimes[minecraft_jvm_os][java_runtime_name][0]["manifest"]["url"]
    #####
    print("Getting the runtime files")

    files = requests.get(files_url).json()["files"]
    for path, file in files.items():
        path = os.path.join(java_runtime_path, path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if file["type"] == "directory":
            pass # Already created using os.makedirs above
        elif file["type"] == "file":
            raw = file["downloads"]["raw"]
            download(raw["url"], path, raw["sha1"])
            if file["executable"]:
                make_executable(path)
        elif file["type"] == "link":
            try: os.symlink(file["target"], path)
            except: pass
        else:
            raise Exception(f"Unrecognized runtime file type: \"{file['type']}\" at \"{path}\"")

    #####
    print("Checking the client")

    try: os.mkdir(version_id)
    except: pass
    os.chdir(version_id)
    try: os.mkdir("libraries")
    except: pass
    try: os.mkdir(os.path.join("libraries", "natives"))
    except: pass
    try: os.mkdir("state")
    except: pass

    library_paths = []

    NATIVES_DIR_PATH = os.path.join("libraries", "natives")

    client = version["downloads"]["client"]
    download(client["url"], "client.jar", client["sha1"])

    #####
    print("Checking the libraries")

    for index, library in enumerate(version["libraries"]):
        if "rules" in library:
            allowed = False
            for rule in library["rules"]:
                if "os" in rule:
                    if rule["os"]["name"] == current_os_name:
                        allowed = rule["action"] == "allow"
                else:
                    allowed = rule["action"] == "allow"
            if not allowed:
                continue

        try:
            artifact = library["downloads"]["artifact"]
        except KeyError:
            pass
        else:
            provided_artifact_path = artifact["path"]
            artifact_name = os.path.basename(provided_artifact_path)
            actual_artifact_path = os.path.join("libraries", f"{index}-{artifact_name}")
            download(artifact["url"], actual_artifact_path, artifact["sha1"])
            library_paths.append(actual_artifact_path)

        try:
            natives = library["downloads"]["classifiers"][f"natives-{current_os_name}"]
        except KeyError:
            pass
        else:
            download(natives["url"], "natives.jar", natives["sha1"])
            with zipfile.ZipFile("natives.jar") as f:
                for member in f.namelist():
                    if member != "META-INF":
                        f.extract(member, NATIVES_DIR_PATH)
            os.remove("natives.jar")

    #####
    print("Writing the lighthouse data file")

    class_path = ["client.jar"] + library_paths
    java_binary_name = "java"
    if current_os_name == "windows":
        java_binary_name = "javaw.exe"
    with open(LIGHTHOUSE_CONFIG_NAME, "w") as f:
        json.dump(
            {
                "lighthouse_version_id": LIGHTHOUSE_VERSION_ID,
                "run_arguments": [
                    "-cp",
                    os.pathsep.join(class_path),
                    "-Djava.library.path=" + NATIVES_DIR_PATH,
                    version["mainClass"],
                    "--gameDir",
                    "state",
                ],
                "java_binary_path": os.path.join("..", java_runtime_path, "bin", java_binary_name),
            },
            f,
            indent=4,
        )

main()
