#!/bin/bash
set -e

# shellcheck disable=SC2035
sudo chmod -R 755 * || chmod -R 755 *

echo "START RUN APP (debug active)"
#If we are trying to inject the library on the "restore" or "build" command we should show the traces
export DD_APM_INSTRUMENTATION_DEBUG=false
export DOTNET_DbgEnableMiniDump=1
export DOTNET_DbgMiniDumpType=4
export DOTNET_CreateDumpDiagnostics=1
export DOTNET_DbgMiniDumpName=/var/log/datadog/dotnet/coredump.txt

if ! command -v systemctl &> /dev/null
then
    sed -i "s/net7.0/net6.0/g" MinimalWebApp.csproj 
    dotnet restore
    dotnet build -c Release
    dotnet publish -c Release -o /home/datadog/publish
    chmod 755 test-app-dotnet_daemon.sh
    chmod 777 /shared_volume/std.out
    ./test-app-dotnet_daemon.sh start
 else
    sudo sed -i "s/net7.0/net6.0/g" MinimalWebApp.csproj 
    dotnet restore
    dotnet build -c Release
    sudo dotnet publish -c Release -o /home/datadog/publish

    export DD_APM_INSTRUMENTATION_DEBUG=true
    sudo cp test-app.service /etc/systemd/system/test-app.service
    sudo systemctl daemon-reload
    sudo systemctl enable test-app.service
    sudo systemctl start test-app.service
    sudo systemctl status test-app.service
fi


echo "RUN DONE"
