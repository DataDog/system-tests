ARG BASE_IMAGE

FROM ${BASE_IMAGE}
WORKDIR /app
COPY lib-injection/build/docker/python/dd-lib-python-init-test-django/ .
ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE django_app
ENV HOME  /root
ENV PYENV_ROOT $HOME/.pyenv
ENV PATH $PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH
ARG PIP_INDEX_URL=https://depot-read-api-python.us1.ddbuild.io/datadog/python/@current/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
# pip 22.3 to 23.1 crashes on JSON simple API pages that serve dist-info-metadata as a dict.
# Upgrade it to a hash-pinned pip first: hash checking skips the metadata lookup that crashes.
RUN if python -c 'import sys, pip; v = tuple(int(x) for x in pip.__version__.split(".")[:2]); sys.exit(not (22, 3) <= v < (23, 2))'; then \
      echo "pip==24.0 --hash=sha256:ba0d021a166865d2265246961bec0152ff124de910c5cc39f1156ce3fa7c69dc" > /tmp/pip-requirements.txt && \
      python -m pip install --require-hashes -r /tmp/pip-requirements.txt; \
    fi
RUN pip install django
EXPOSE 18080
CMD python -m django runserver --noreload 0.0.0.0:18080
