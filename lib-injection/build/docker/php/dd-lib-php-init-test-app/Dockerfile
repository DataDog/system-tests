FROM public.ecr.aws/docker/library/php:8.3

RUN mkdir /app
WORKDIR /app

COPY index.php /app

CMD ["php", "-S", "0.0.0.0:18080"]
