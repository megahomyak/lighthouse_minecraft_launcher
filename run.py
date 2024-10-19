import os

class_path = ["version/client.jar"]
for file_name in os.listdir("version/libraries"):
    class_path.append(f"version/libraries/{file_name}")
command = f"java -cp {':'.join(class_path)} -Djava.library.path=version/libraries net.minecraft.client.Minecraft"
print(command)
print()
os.system(command)
