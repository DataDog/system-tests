#!/bin/bash
set -e
chmod -R 755 * || true

echo "START RUN APP"

sudo sed -i "s/net7.0/net6.0/g" MinimalWebApp.csproj 
dotnet restore
dotnet build -c Release
dotnet publish -c Release -o ~/publish


sudo sed -i "s/MY_USER/$(whoami)/g" test-app-dotnet.service 
sudo cp test-app-dotnet.service /etc/systemd/system/test-app-dotnet.service
sudo systemctl daemon-reload
sudo systemctl enable test-app-dotnet.service
sudo systemctl start test-app-dotnet.service
sudo systemctl status test-app-dotnet.service
echo "RUN DONE"
