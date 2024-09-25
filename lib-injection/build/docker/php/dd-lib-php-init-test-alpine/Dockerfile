FROM public.ecr.aws/docker/library/alpine:3.20

RUN apk add --update php83 libgcc libcurl bash

RUN mkdir /app
WORKDIR /app

COPY index.php /app

ENV DD_TRACE_DEBUG 1

CMD ["php","-S","0.0.0.0:18080"]
