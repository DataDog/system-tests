#!/bin/bash
set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

echo "START dotnet APP (debug active)"

#workaround. Remove the system-tests cloned folder. The sources are copied to current home folder
#if we don't remove it, the dotnet restore will try to restore the system-tests folder
sudo rm -rf system-tests

#Restore, build and publish the app
sudo dotnet publish -c Release -o /home/datadog

#Copy app service and start it
sudo chmod 755 create_and_run_app_service.sh
./create_and_run_app_service.sh "dotnet MinimalWebApp.dll" "ASPNETCORE_URLS=http://+:5985 DD_APM_INSTRUMENTATION_DEBUG=true COMPlus_DbgEnableMiniDump=1 DOTNET_DbgEnableMiniDump=1 COMPlus_DbgMiniDumpType=4 DOTNET_DbgMiniDumpType=4 COMPlus_CreateDumpDiagnostics=1  DOTNET_CreateDumpDiagnostics=1 COMPlus_DbgMiniDumpName=/var/log/datadog/dotnet/coredump.%t.%p.log DOTNET_DbgMiniDumpName=/var/log/datadog/dotnet/coredump.%t.%p.log  COMPlus_EnableCrashReport=1  DOTNET_EnableCrashReport=1"

echo "RUN dotnet DONE"