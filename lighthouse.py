import json
import os
import sys
import urllib.request
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
    with urllib.request.urlopen(url) as response:
        return json.load(response)

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

def ensure_json(url, path, expected_sha1_in_hex):
    download(url, path, expected_sha1_in_hex)
    with open(path) as f:
        return json.load(f)

def list_():
    versions_list = get_versions_list()
    print("LATEST:")
    print("* Release: " + versions_list["latest"]["release"])
    print("* Snapshot: " + versions_list["latest"]["snapshot"])
    print()
    for version in versions_list["versions"]:
        print(f"{version['id']} - {version['type'].upper()}")

def get_version_path(version_id):
    return os.path.join("versions", version_id)

def run(version_id):
    os.chdir(get_version_path(version_id))
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
    #####
    print("Writing the Lighthouse warning file")

    with open("WARNING_READ_ME.txt", "w") as f:
        f.write("This directory is used for the Lighthouse Minecraft launcher. Please, only modify the state of Minecraft version instances. Every other modification may break Lighthouse operations.")

    #####
    versions_list = get_versions_list()["versions"]
    for version in versions_list:
        if version["id"] == version_id:
            break
    else:
        raise Exception(f"Can't find version {version_id}")

    #####
    print("Checking the directory structure")

    def mkdir(path):
        try: os.mkdir(path)
        except: pass
        return path
    versions_path = mkdir("versions")
    version_path = get_version_path(version_id)
    libraries_path = mkdir("libraries")
    natives_path = mkdir("native_libraries")
    state_path = mkdir(os.path.join(version_path, "state"))
    assets_path = mkdir("assets")
    runtimes_path = mkdir("runtimes")

    #####
    print("Checking the version JSON")

    version = ensure_json(version["url"], os.path.join(versions_path, version_id + ".json"), version["sha1"])

    #####
    print("Checking the runtime directory")

    java_runtime_name = version["javaVersion"]["component"]
    java_runtime_path = mkdir(os.path.join(runtimes_path, java_runtime_name))

    #####
    print("Getting the runtimes list")

    runtimes = download_json("https://launchermeta.mojang.com/v1/products/java-runtime/2ec0cc96c44e5a76b9c8b7c39df7210883d12871/all.json")
    manifest = runtimes[minecraft_jvm_os][java_runtime_name][0]["manifest"]

    #####
    print("Checking the runtime files")

    runtime = ensure_json(manifest["url"], os.path.join(runtimes_path, java_runtime_name + ".json"), manifest["sha1"])

    for path, file in runtime["files"].items():
        path = os.path.join(java_runtime_path, path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if file["type"] == "directory":
            try: os.mkdir(path)
            except: pass
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

    client = version["downloads"]["client"]
    download(client["url"], os.path.join(version_path, "client.jar"), client["sha1"])

    #####
    print("Checking the libraries")

    library_paths = []

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
            path = os.path.join(libraries_path, artifact["path"])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            download(artifact["url"], path, artifact["sha1"])
            library_paths.append(path)

        try:
            natives = library["downloads"]["classifiers"][f"natives-{current_os_name}"]
        except KeyError:
            pass
        else:
            path = os.path.join(libraries_path, natives["path"])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            download(natives["url"], path, natives["sha1"])
            with zipfile.ZipFile(path) as f:
                for member in f.namelist():
                    for excluded in library["extract"]["exclude"]:
                        if member.startswith(excluded):
                            break
                    else:
                        f.extract(member, natives_path)

    #####
    print("Checking the assets")

    assets = version["assetIndex"]
    assets_index = assets["id"]
    if assets_index == "pre-1.6":
        assets_index = None
        assets_index_path = mkdir(os.path.join(state_path, "resources"))
        assets_json_name = version_id + ".json"
    else:
        assets_index_path = mkdir(os.path.join(assets_path, assets_index))
        assets_json_name = assets_index + ".json"
    assets_json_path = os.path.join(assets_path, assets_json_name)
    assets_json = ensure_json(assets["url"], assets_json_path, assets["sha1"])
    for asset_path, asset_info in assets_json["objects"].items():
        hash_ = asset_info["hash"]
        prefix = hash_[:2]
        asset_path = os.path.join(assets_index_path, asset_path)
        os.makedirs(os.path.dirname(asset_path), exist_ok=True)
        download(f"https://resources.download.minecraft.net/{prefix}/{hash_}", asset_path, hash_)

    #####
    print("Checking the Lighthouse data file... ", end="", flush=True)

    lighthouse_config_path = os.path.join(version_path, LIGHTHOUSE_CONFIG_NAME)
    if os.path.exists(lighthouse_config_path):
        print("EXISTS")
    else:
        print("CREATING")
        root_path = os.path.join("..", "..")
        class_path = ["client.jar"] + [
            os.path.join(root_path, path)
            for path in library_paths
        ]
        java_binary_name = "java"
        if current_os_name == "windows":
            java_binary_name = "javaw.exe"
        run_arguments = [
            "-cp", os.pathsep.join(class_path),
            "-Djava.library.path=" + os.path.join(root_path, natives_path),
            version["mainClass"],
            "--gameDir", "state",
        ]
        if assets_index is not None:
            run_arguments.extend([
                "--assetsDir", assets_path,
                "--assetIndex", assets_index,
            ])
        with open(lighthouse_config_path, "w") as f:
            json.dump(
                {
                    "lighthouse_version_id": LIGHTHOUSE_VERSION_ID,
                    "run_arguments": run_arguments,
                    "java_binary_path": os.path.join(root_path, java_runtime_path, "bin", java_binary_name),
                },
                f,
                indent=4,
            )

main()
