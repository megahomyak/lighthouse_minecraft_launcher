import os

class_path = ["version/client.jar"]
for file_name in os.listdir("version/library"):
    class_path.append(f"version/library/{file_name}")
command = f"java -cp {':'.join(class_path)} net.minecraft.client.Minecraft"
print(command)
os.system(command)
