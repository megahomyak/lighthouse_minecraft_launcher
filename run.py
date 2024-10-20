import os

class_path = ["$(realpath version/client.jar)"]
for file_name in os.listdir("version/libraries"):
    class_path.append(f"$(realpath version/libraries/{file_name})")
command = f"java -cp {':'.join(class_path)} -Djava.library.path=$(realpath version/libraries) net.minecraft.client.Minecraft"
print(command)
print()
os.system(command)
