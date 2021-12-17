FROM alpine


RUN apk add --no-cache --upgrade bash
RUN apk add php php-json

WORKDIR /app

RUN wget https://dd.datad0g.com/security/appsec/event-rules
RUN mv event-rules event-rules.json

RUN echo '<?php phpinfo(); ?>' > index.php

ENV DD_TRACE_ENABLED=true
ENV DD_TRACE_NO_AUTOLOADER=true

CMD ["php", "-f","index.php","-S","0.0.0.0:7777"]

EXPOSE 7777

ENV DD_TRACE_SAMPLE_RATE=0.5
ENV DD_TAGS='key1:val1, key2 : val2 '

COPY utils/build/docker/php/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
