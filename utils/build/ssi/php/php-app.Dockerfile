ARG BASE_IMAGE

FROM ${BASE_IMAGE}
WORKDIR /app

COPY index.php .

# Without the sleep, the docker network has issues
CMD ["sh", "-c", "sleep 2; php -S 0.0.0.0:18080"]
