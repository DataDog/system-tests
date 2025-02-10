ARG BASE_IMAGE

FROM ${BASE_IMAGE}
WORKDIR /app
# Keep the container running
CMD ["tail", "-f", "/dev/null"]
