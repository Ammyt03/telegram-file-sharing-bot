modules = ["python-3.11", "postgresql-16", "python3"]

[nix]
channel = "stable-24_05"

[workflows]
runButton = "Project"

[[workflows.workflow]]
name = "Project"
mode = "parallel"
author = "agent"

[[workflows.workflow.tasks]]
task = "workflow.run"
args = "Bot"

[[workflows.workflow]]
name = "Bot"
author = "agent"

[[workflows.workflow.tasks]]
task = "shell.exec"
args = "python main.py"
waitForPort = 5000

[[ports]]
localPort = 5000
externalPort = 80

[deployment]
deploymentTarget = "cloudrun"
run = ["sh", "-c", "python main.py"]
