ARG BASE_IMAGE

FROM ${BASE_IMAGE}
WORKDIR /app

RUN printf "<?php\necho'hi';\n" > index.php

CMD ["php","-S","0.0.0.0:18080"]
