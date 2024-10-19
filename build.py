import json
import requests
import os

def download(directory, url):
    os.system(f"mkdir -p {directory}")
    os.system(f"wget {url} -O {directory}/$(basename {url})")

version = requests.get("https://piston-meta.mojang.com/v1/packages/924a2dcd8bdc31f8e9d36229811c298b3537bbc7/1.5.2.json").json()
download("version", version["downloads"]["client"]["url"])
for library in version["libraries"]:
    try: download("version/library", library["downloads"]["artifact"]["url"])
    except KeyError: pass

    try: download("version/library", library["downloads"]["classifiers"]["natives-linux"]["url"])
    except KeyError: pass
