import os

class_path = ["version/client.jar"]
for file_name in os.listdir("version/libraries"):
    class_path.append(f"version/libraries/{file_name}")
command = f"/usr/lib/jvm/java-8-openjdk-amd64/bin/java -cp {':'.join(class_path)} -Djava.library.path=version/libraries/natives net.minecraft.launchwrapper.Launch --gameDir version/state"
print(command)
print()
os.system(command)
