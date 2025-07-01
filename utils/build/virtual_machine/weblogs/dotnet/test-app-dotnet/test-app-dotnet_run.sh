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

#workaround. Remove the system-tests cloned folder. The sources are copied to current home folder
#if we don't remove it, the dotnet restore will try to restore the system-tests folder
sudo rm -rf system-tests

#Restore, build and publish the app
dotnet restore
dotnet build -c Release 
sudo dotnet publish -c Release -o /home/datadog

detect_glibc() {
  # 1) getconf
  if v=$(getconf GNU_LIBC_VERSION 2>/dev/null); then
    echo "${v#* }" && return
  fi
  # 2) ldd
  if v=$(ldd --version 2>&1 | head -n1 | grep -oE '[0-9]+\.[0-9]+'); then
    echo "$v" && return
  fi
  # 3) direct libc.so.6
  for lib in /lib*/libc.so.6; do
    if [ -x "$lib" ]; then
      out=$("$lib" 2>&1 | head -n1)
      if [[ $out =~ version\ ([0-9]+\.[0-9]+) ]]; then
        echo "${BASH_REMATCH[1]}" && return
      fi
    fi
  done
  # fallback
  echo ""
}

glibc_ver=$(detect_glibc)
echo "GLIBC_VER: $glibc_ver"


#Copy app service and start it
export DD_APM_INSTRUMENTATION_DEBUG=true
sudo chmod 755 create_and_run_app_service.sh
./create_and_run_app_service.sh "dotnet MinimalWebApp.dll" "ASPNETCORE_URLS=http://+:5985 DOTNET_DbgEnableMiniDump=1 DOTNET_DbgMiniDumpType=4 DOTNET_DbgMiniDumpName=/var/log/datadog/dotnet/coredump.%p.dmp"

echo "RUN dotnet DONE"