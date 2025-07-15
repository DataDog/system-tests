FROM public.ecr.aws/docker/library/ruby:3.1.3

ENV DEBIAN_FRONTEND=noninteractive

# Install prerequisites
RUN set -ex && \
  echo "===> Installing dependencies" && \
  apt-get -y update && \
  apt-get install -y --force-yes --no-install-recommends \
      curl wget tar gzip gnupg apt-transport-https ca-certificates tzdata locales && \
  \
  echo "===> Installing database libraries" && \
  apt-get install -y --force-yes --no-install-recommends sqlite3 && \
  \
  echo "===> Installing dev tools" && \
  mkdir -p /usr/share/man/man1 && \
  apt-get install -y --force-yes --no-install-recommends \
      sudo git openssh-client rsync vim \
      net-tools netcat parallel unzip zip bzip2 && \
  \
  echo "===> Cleaning up" && \
  rm -rf /var/lib/apt/lists/*;

# Set timezone to UTC by default
RUN ln -sf /usr/share/zoneinfo/Etc/UTC /etc/localtime

# Set language
RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en

# Upgrade RubyGems and Bundler
RUN gem update --system 3.4.1
RUN gem install bundler -v '~> 2.3.26'
RUN mkdir -p "$GEM_HOME" && chmod -R 777 "$GEM_HOME"
ENV BUNDLE_SILENCE_ROOT_WARNING 1

# Setup directory
RUN mkdir /app
WORKDIR /app

# Add files
COPY lib_injection_rails_app /app

# Replace with other gemfile and configure bundler to use it
RUN mv Gemfile TestGemfile && mv Gemfile.lock TestGemfile.lock
ENV BUNDLE_GEMFILE TestGemfile

# Install gems
RUN bundle install

# Set entrypoint
ENTRYPOINT ["/bin/bash", "-c"]

CMD ["bundle exec rails server -b 0.0.0.0 -p 18080"]

