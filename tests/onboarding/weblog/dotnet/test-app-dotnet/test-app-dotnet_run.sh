#!/bin/bash
set -e
sudo chmod -R 755 *

echo "START RUN APP"
#If we are trying to inject the library on the "restore" or "build" command we should show the traces
export DD_APM_INSTRUMENTATION_DEBUG=TRUE
sudo sed -i "s/net7.0/net6.0/g" MinimalWebApp.csproj 
dotnet restore
dotnet build -c Release
sudo dotnet publish -c Release -o /home/datadog/publish


sudo cp test-app-dotnet.service /etc/systemd/system/test-app-dotnet.service
sudo systemctl daemon-reload
sudo systemctl enable test-app-dotnet.service
sudo systemctl start test-app-dotnet.service
sudo systemctl status test-app-dotnet.service
echo "RUN DONE"
