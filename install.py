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

LIGHTHOUSE_VERSION_ID = "megahomyak-1"
LIGHTHOUSE_CONFIG_NAME = "lighthouse.config.json"

TEN_MEGABYTES_IN_BYTES = 1 * 1024 * 1024 * 10

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
    return download_json("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json")

def make_executable(file_path):
    st = os.stat(file_path)
    os.chmod(file_path, st.st_mode | stat.S_IEXEC)

def main():
    action = sys.argv[1]
    if action == "list":
        list_()
    elif action == "install":
        version_id = sys.argv[2]
        install(version_id)
    elif action == "run":
        version_id = sys.argv[2]
        run(version_id)
    else:
        raise Exception(f"Invalid action name \"{action}\"")

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
        subprocess.run([java_binary_path, *arguments])
    else:
        raise Exception(f"Bad config version: expected {LIGHTHOUSE_VERSION_ID}, got {config_lighthouse_version_id}")

def install(version_id):
    versions_list = get_versions_list()["versions"]
    for version in versions_list:
        if version["id"] == version_id:
            version_url = version["url"]
            break
    else:
        raise Exception(f"Can't find version {version_id}")

    with open("WARNING_READ_ME.txt", "w") as f:
        f.write("This directory is being used for storing Minecraft instances of the Lighthouse Minecraft launcher. Modifying this directory manually (that is, not through Lighthouse) might prevent Lighthouse from functioning well here. All file-dependant calls to Lighthouse should be done from this directory.")

    version = requests.get(version_url).json()

    #####
    print("Installing the runtime")

    java_runtime_name = version["javaVersion"]["component"]
    java_runtime_path = os.path.join("runtimes", java_runtime_name)
    try:
        os.makedirs(java_runtime_path, exist_ok=False)
    except FileExistsError:
        pass
    else:
        runtimes = requests.get("https://launchermeta.mojang.com/v1/products/java-runtime/2ec0cc96c44e5a76b9c8b7c39df7210883d12871/all.json").json()
        files_url = runtimes[minecraft_jvm_os][java_runtime_name][0]["manifest"]["url"]
        files = requests.get(files_url).json()["files"]
        for path, file in files.items():
            path = os.path.join(java_runtime_path, path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if file["type"] == "directory":
                pass # Already created using os.makedirs above
            elif file["type"] == "file":
                file_url = file["downloads"]["raw"]["url"]
                print(f"Downloading {file_url}")
                urllib.request.urlretrieve(file_url, path)
                if file["executable"]:
                    make_executable(path)
            elif file["type"] == "link":
                os.symlink(file["target"], path)
            else:
                raise Exception(f"Unrecognized runtime file type: \"{file['type']}\" at \"{path}\"")

    #####
    print("Installing the client")

    shutil.rmtree(version_id, ignore_errors=True)
    os.mkdir(version_id)
    os.chdir(version_id)
    os.mkdir("libraries")
    os.mkdir(os.path.join("libraries", "natives"))
    os.mkdir("state")

    library_paths = []

    NATIVES_DIR_PATH = os.path.join("libraries", "natives")

    client_url = version["downloads"]["client"]["url"]
    print(f"Downloading {client_url}")
    urllib.request.urlretrieve(client_url, "client.jar")

    #####
    print("Installing the libraries")

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
            artifact_url = library["downloads"]["artifact"]["url"]
        except KeyError:
            pass
        else:
            provided_artifact_path = library["downloads"]["artifact"]["path"]
            artifact_name = os.path.basename(provided_artifact_path)
            actual_artifact_path = os.path.join("libraries", f"{index}-{artifact_name}")
            print(f"Downloading {artifact_url}")
            urllib.request.urlretrieve(artifact_url, actual_artifact_path)
            library_paths.append(actual_artifact_path)

        try:
            natives_url = library["downloads"]["classifiers"][f"natives-{current_os_name}"]["url"]
        except KeyError:
            pass
        else:
            natives_jar_path = os.path.join(NATIVES_DIR_PATH, "natives.jar")
            print(f"Downloading {natives_url}")
            urllib.request.urlretrieve(natives_url, natives_jar_path)
            with zipfile.ZipFile(natives_jar_path) as f:
                for member in f.namelist():
                    if member != "META-INF":
                        f.extract(member, NATIVES_DIR_PATH)
            os.remove(natives_jar_path)

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
