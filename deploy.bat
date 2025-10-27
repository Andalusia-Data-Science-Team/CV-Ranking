@echo off
echo ===== Deploying CV-Ranker to Linux Server =====

scp -r "D:\New Website\new rag\Repo\CV-Ranker\*" ai@10.24.105.221:/home/ai/CV-Ranker/

ssh ai@10.24.105.221 "bash /home/ai/CV-Ranker/restart.sh"

echo ===== Deployment Complete =====
pause


:: .\deploy.bat