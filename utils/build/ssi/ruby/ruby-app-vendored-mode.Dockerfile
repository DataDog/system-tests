ARG BASE_IMAGE

FROM ${BASE_IMAGE}
WORKDIR /app
COPY lib-injection/build/docker/ruby/lib_injection_rails_app/ .
RUN rm -vf .ruby-version
ENV HOME  /root
ENV RBENV_ROOT $HOME/.rbenv
ENV PATH $RBENV_ROOT/shims:$RBENV_ROOT/bin:$PATH
ENV BUNDLE_PATH=/bundle
RUN env DD_APM_INSTRUMENTATION_DEBUG=false bundle install && rbenv rehash
EXPOSE 18080
CMD bin/rails server -b 0.0.0.0 -p 18080
