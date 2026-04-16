
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build-app
WORKDIR /app

# Opt-out of .NET SDK CLI telemetry
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1

# dotnet restore
COPY utils/build/docker/dotnet/parametric/ApmTestApi.csproj utils/build/docker/dotnet/parametric/nuget.config ./
RUN dotnet restore "./ApmTestApi.csproj"

# dotnet publish
COPY utils/build/docker/dotnet/parametric ./
RUN dotnet publish --no-restore -c Release -o out

##################

FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build-version-tool
WORKDIR /app

# Opt-out of .NET SDK CLI telemetry
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1

COPY utils/build/docker/dotnet/parametric/../GetAssemblyVersion ./
RUN dotnet publish -c Release -o out

##################

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y curl locales gcc libc6-dev \
    && echo "de_DE.UTF-8 UTF-8" >> /etc/locale.gen && locale-gen \
    && printf '#include <locale.h>\n#include <stdlib.h>\n__attribute__((constructor)) static void init_locale(void){const char*l=getenv("TEST_LOCALE");if(l&&*l)setlocale(LC_ALL,l);}' > /tmp/li.c \
    && gcc -shared -fPIC -o /locale_init.so /tmp/li.c \
    && rm /tmp/li.c && rm -rf /var/lib/apt/lists/*

# install dd-trace-dotnet (must be done before setting LD_PRELOAD)
COPY utils/build/docker/dotnet/install_ddtrace.sh binaries/ /binaries/
RUN /binaries/install_ddtrace.sh

# Opt-out of .NET SDK CLI telemetry (prevent unexpected http client spans)
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1

# Set up automatic instrumentation
ENV CORECLR_ENABLE_PROFILING=1
ENV CORECLR_PROFILER='{846F5F1C-F9AE-4B07-969E-05C26BC060D8}'
ENV CORECLR_PROFILER_PATH=/opt/datadog/Datadog.Trace.ClrProfiler.Native.so
# LD_PRELOAD for continuous profiler: the ApiWrapper.x64.so is x86_64-only
# and crashes immediately on ARM.  Set it conditionally via an entrypoint
# wrapper so the image works on both architectures.
ENV DD_DOTNET_TRACER_HOME=/opt/datadog

# disable gRPC, ASP.NET Core, and other auto-instrumentations (to prevent unexpected spans)
ENV DD_TRACE_Grpc_ENABLED=false
ENV DD_TRACE_AspNetCore_ENABLED=false
ENV DD_TRACE_Process_ENABLED=false

# copy custom tool used to get library version (built above)
COPY utils/build/docker/dotnet/parametric/system_tests_library_version.sh ./
COPY --from=build-version-tool /app/out /app

# copy the dotnet app (built above)
COPY --from=build-app /app/out /app

RUN mkdir /parametric-tracer-logs

# Conditionally set LD_PRELOAD at runtime — the x64 ApiWrapper .so does not
# exist on ARM and would crash the container if set unconditionally.
COPY utils/build/docker/dotnet/parametric/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["./ApmTestApi"]
