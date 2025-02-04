#!/bin/bash
#Build docker templates and load them into the buildah
#These images will be used by the krunvm provider to lauch the onboarding tests locally

docker build -t amazonlinux_datadog:2023 -f Dockerfile.amazonlinux2023 . 
buildah from --root /Volumes/krunvm/root --runroot /Volumes/krunvm/runroot docker-daemon:amazonlinux_datadog:2023

docker build -t ubuntu_datadog:22 -f Dockerfile.ubuntu22 . 
buildah from --root /Volumes/krunvm/root --runroot /Volumes/krunvm/runroot docker-daemon:ubuntu_datadog:22