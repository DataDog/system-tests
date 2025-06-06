ARG BASE_IMAGE

FROM ${BASE_IMAGE}
WORKDIR /app
COPY lib-injection/build/docker/python/dd-lib-python-init-test-django/ .
ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE django_app
ENV HOME  /root
ENV PYENV_ROOT $HOME/.pyenv
ENV PATH $PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH
RUN pip install django
EXPOSE 18080
CMD python -m django runserver --noreload 0.0.0.0:18080
