FROM registry.ddbuild.io/images/docker:20.10.13-jammy

# For more information see https://datadoghq.atlassian.net/wiki/spaces/SECENG/pages/5138645099/User+guide+dd-octo-sts#%3Agitlab%3A-Via-Gitlab-CI-job
COPY --from=registry.ddbuild.io/dd-octo-sts:v1.9.3@sha256:f8412df42db2e1879182c820ea4ef600ab4375c5b696a24151c7f0dd931ffee6 /usr/local/bin/dd-octo-sts /usr/local/bin/dd-octo-sts

RUN apt-get update && apt-get -y install awscli
RUN aws --version && docker --version

# To build:
# docker buildx build --platform linux/amd64 -f utils/build/docker/base-image-builder.Dockerfile -t registry.ddbuild.io/system-tests/base-image-builder:latest --push .
