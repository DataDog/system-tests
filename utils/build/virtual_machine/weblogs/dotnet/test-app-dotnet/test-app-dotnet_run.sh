#!/bin/bash
set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

echo "START RUN APP (debug active)"
#If we are trying to inject the library on the "restore" or "build" command we should show the traces
export DD_APM_INSTRUMENTATION_DEBUG=false
export DOTNET_DbgEnableMiniDump=1
export DOTNET_DbgMiniDumpType=4
export DOTNET_CreateDumpDiagnostics=1
export DOTNET_DbgMiniDumpName=/var/log/datadog/dotnet/coredump.txt

#This is the output for the app service
sudo touch /home/datadog/app-std.out
sudo chmod 777 /home/datadog/app-std.out

#We are running the app for dotnet 6.0
sudo sed -i "s/net7.0/net6.0/g" MinimalWebApp.csproj 

#Restore, build and publish the app
dotnet restore
dotnet build -c Release 
dotnet publish -c Release -o /home/datadog/publish

#Copy app service and start it
export DD_APM_INSTRUMENTATION_DEBUG=true
sudo cp test-app.service /etc/systemd/system/test-app.service
sudo systemctl daemon-reload
sudo systemctl enable test-app.service
sudo systemctl start test-app.service
sudo systemctl status test-app.service

#Wait for the app to start and show the logs
sleep 5
cat /home/datadog/app-std.out

echo "RUN DONE"
