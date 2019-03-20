import os

print(os.getcwd())
os.chdir('/secrets')
os.chdir(os.path.dirname(os.path.abspath(__file__)))
print(os.getcwd())
