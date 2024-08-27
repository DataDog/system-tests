#!/bin/bash
set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

echo "START dotnet APP (debug active)"
#If we are trying to inject the library on the "restore" or "build" command we should show the traces
export DD_APM_INSTRUMENTATION_DEBUG=false
export DOTNET_DbgEnableMiniDump=1
export DOTNET_DbgMiniDumpType=4
export DOTNET_CreateDumpDiagnostics=1
export DOTNET_DbgMiniDumpName=/var/log/datadog/dotnet/coredump.txt

#We are running the app for dotnet 6.0
sudo sed -i "s/net7.0/net6.0/g" MinimalWebApp.csproj 

#Restore, build and publish the app
dotnet restore
dotnet build -c Release 
sudo dotnet publish -c Release -o /home/datadog

#Copy app service and start it
export DD_APM_INSTRUMENTATION_DEBUG=true
sudo chmod 755 create_and_run_app_service.sh
./create_and_run_app_service.sh "dotnet MinimalWebApp.dll" "ASPNETCORE_URLS=http://+:5985 DOTNET_DbgEnableMiniDump=1 DOTNET_DbgMiniDumpType=4"

echo "RUN dotnet DONE"