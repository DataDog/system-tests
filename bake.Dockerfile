# syntax = docker/dockerfile:1.4.0
FROM scratch as runner

FROM runner as builder

RUN set -xe; \
    cat <<EOF >> exec_gen_step.sh
#!/bin/bash
    set -xe
    TARGET_DIR=\$1
    SCENARIO_SUFIX=\$(echo "\$SCENARIO" | tr '[:upper:]' '[:lower:]')
    ONBOARDING_FILTER_ENV="\$FILTER_ENV"
    DD_INSTALLER_LIBRARY_VERSION="\$INSTALLER_LIBRARY_VERSION"
    DD_INSTALLER_INJECTOR_VERSION="\$INSTALLER_INJECTOR_VERSION"
    env


    ./run.sh \$SCENARIO --vm-weblog \${ONBOARDING_FILTER_WEBLOG} --vm-env \${ONBOARDING_FILTER_ENV} --vm-library \${TEST_LIBRARY} --vm-provider aws --vm-default-vms All --vm-gitlab-pipeline system-tests

    mkdir -p reports/logs_"\${SCENARIO_SUFIX}_\${ONBOARDING_FILTER_WEBLOG}"
    cp -R logs_"\${SCENARIO_SUFIX}"/gitlab_pipeline.yml reports/logs_"\${SCENARIO_SUFIX}_\${ONBOARDING_FILTER_WEBLOG}"
EOF

ENV DD_API_KEY_ONBOARDING=xyz
ENV DD_APP_KEY_ONBOARDING=xyz
ENV FILTER_ENV="prod"

FROM builder as output_1

ENV TEST_LIBRARY="java"
ENV ONBOARDING_FILTER_WEBLOG="test-app-java"
ENV SCENARIO="HOST_AUTO_INJECTION_INSTALL_SCRIPT"
RUN set -ex; bash ./exec_gen_step.sh /app/reports

ENV SCENARIO=HOST_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING
RUN set -ex; bash ./exec_gen_step.sh /app/reports

ENV ONBOARDING_FILTER_WEBLOG=test-app-java-multicontainer
ENV SCENARIO=CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT
RUN set -ex; bash ./exec_gen_step.sh /app/reports

ENV SCENARIO=CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING
RUN set -ex; bash ./exec_gen_step.sh /app/reports


# # ---
# ENV ONBOARDING_FILTER_WEBLOG="test-app-java"
# ENV SCENARIO="HOST_AUTO_INJECTION_INSTALL_SCRIPT"

#     # matrix:
#     #     - ONBOARDING_FILTER_WEBLOG: [test-app-java]
#     #       SCENARIO:
#     #         - HOST_AUTO_INJECTION_INSTALL_SCRIPT
#     #         - HOST_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING
#     #     - ONBOARDING_FILTER_WEBLOG: [test-app-java-multicontainer,test-app-java-multialpine]
#     #       SCENARIO:
#     #         - CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT
#     #         - CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING
#     #     - ONBOARDING_FILTER_WEBLOG: [test-app-java,test-app-java-container,test-app-java-alpine,test-app-java-buildpack]
#     #       SCENARIO: [INSTALLER_AUTO_INJECTION]
#     #     - ONBOARDING_FILTER_WEBLOG: [test-app-java,test-app-java-multicontainer,test-app-java-multialpine]
#     #       SCENARIO: [SIMPLE_AUTO_INJECTION_PROFILING]
#     #     - ONBOARDING_FILTER_WEBLOG: [test-app-java]
#     #       SCENARIO: [CHAOS_INSTALLER_AUTO_INJECTION]
#     #     - ONBOARDING_FILTER_WEBLOG: [test-app-java-multicontainer,test-app-java-multialpine]
#     #       SCENARIO: [SIMPLE_INSTALLER_AUTO_INJECTION]

# # ---


# ENV TEST_LIBRARY="nodejs"
# ENV ONBOARDING_FILTER_WEBLOG="test-app-nodejs"
# ENV SCENARIO="HOST_AUTO_INJECTION_INSTALL_SCRIPT"
# #Because sometimes I don't want to run all pipeline, I only run step1_xx with env filter param
# ENV ONBOARDING_FILTER_ENV="$FILTER_ENV"
# ENV DD_INSTALLER_LIBRARY_VERSION="$INSTALLER_LIBRARY_VERSION"
# ENV DD_INSTALLER_INJECTOR_VERSION="$INSTALLER_INJECTOR_VERSION"


# RUN set -ex; bash ./exec_gen_step.sh /app/reports

FROM scratch as export
COPY --from=output_1 /app/reports/ /reports
