#!/bin/bash
set -e
sudo chmod -R 755 *

echo "START RUN APP (debug active)"
#If we are trying to inject the library on the "restore" or "build" command we should show the traces
export DD_APM_INSTRUMENTATION_DEBUG=TRUE
export DOTNET_DbgEnableMiniDump=1
export DOTNET_DbgMiniDumpType=4

sudo sed -i "s/net7.0/net6.0/g" MinimalWebApp.csproj 
dotnet restore
dotnet build -c Release
sudo dotnet publish -c Release -o /home/datadog/publish


sudo cp test-app.service /etc/systemd/system/test-app.service
sudo systemctl daemon-reload
sudo systemctl enable test-app.service
sudo systemctl start test-app.service
sudo systemctl status test-app.service
echo "RUN DONE"
