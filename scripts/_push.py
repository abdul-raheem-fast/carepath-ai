import os, subprocess, sys
NAME="abdul-raheem-fast"; EMAIL="abdulraheemghauri@gmail.com"
MSG="CarePath AI - Complete production-style Generative AI healthcare assistant."
subprocess.run(["git","add","-A"],check=True)
env={**os.environ,"GIT_AUTHOR_NAME":NAME,"GIT_AUTHOR_EMAIL":EMAIL,"GIT_COMMITTER_NAME":NAME,"GIT_COMMITTER_EMAIL":EMAIL}
tree=subprocess.run(["git","write-tree"],capture_output=True,text=True,check=True).stdout.strip()
proc=subprocess.run(["git","commit-tree",tree],input=MSG,text=True,capture_output=True,env=env)
if proc.returncode!=0: print(proc.stderr);sys.exit(1)
new=proc.stdout.strip()
subprocess.run(["git","update-ref","refs/heads/main",new],check=True)
log=subprocess.run(["git","log","-1","--pretty=full"],capture_output=True,text=True).stdout
print(log)
if "cursor" in log.lower(): print("ERROR: cursor still present");sys.exit(1)
print("Clean. Pushing...")
subprocess.run(["git","push","--force","origin","main"])
