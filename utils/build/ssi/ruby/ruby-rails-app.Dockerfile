ARG BASE_IMAGE

FROM ${BASE_IMAGE}
WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

# Copy the Ruby Rails app from lib-injection
COPY lib-injection/build/docker/ruby/dd-lib-ruby-init-test-rails/lib_injection_rails_app/ .

# Set environment variables for Rails
ENV RAILS_ENV=production
ENV BUNDLE_SILENCE_ROOT_WARNING=1
ENV RBENV_ROOT="/usr/local/rbenv"
ENV PATH="$RBENV_ROOT/bin:$RBENV_ROOT/shims:$PATH"

# Initialize rbenv and install dependencies at runtime
RUN if [ -f "$RBENV_ROOT/bin/rbenv" ]; then \
        eval "$(rbenv init -)" && \
        bundle install && \
        bundle exec rails assets:precompile; \
    else \
        echo "Ruby not installed yet, will install dependencies at runtime"; \
    fi

# Expose port 18080
EXPOSE 18080

# Create startup script that ensures dependencies are installed
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "=== Ruby Docker SSI Startup Script ==="\n\
\n\
# Set up rbenv environment\n\
export RBENV_ROOT="/usr/local/rbenv"\n\
export PATH="$RBENV_ROOT/bin:$RBENV_ROOT/shims:$PATH"\n\
\n\
# Source rbenv profile if available\n\
if [ -f "/etc/profile.d/rbenv.sh" ]; then\n\
    source /etc/profile.d/rbenv.sh\n\
fi\n\
\n\
# Initialize rbenv\n\
if [ -f "$RBENV_ROOT/bin/rbenv" ]; then\n\
    echo "Initializing rbenv..."\n\
    eval "$(rbenv init -)"\n\
    rbenv rehash\n\
else\n\
    echo "ERROR: rbenv not found at $RBENV_ROOT/bin/rbenv"\n\
    echo "Available Ruby installations:"\n\
    ls -la /usr/bin/ | grep -E "(ruby|gem|bundle)" || echo "No Ruby binaries found in /usr/bin/"\n\
    echo "Available rbenv installations:"\n\
    ls -la /usr/local/ | grep rbenv || echo "No rbenv found in /usr/local/"\n\
    exit 1\n\
fi\n\
\n\
# Verify Ruby and bundle are available\n\
echo "Ruby version: $(ruby --version || echo \"Ruby not found\")"\n\
echo "Gem version: $(gem --version || echo \"Gem not found\")"\n\
echo "Bundle version: $(bundle --version || echo \"Bundle not found\")"\n\
echo "Current PATH: $PATH"\n\
echo "RBENV_ROOT: $RBENV_ROOT"\n\
\n\
# Check if bundle command exists\n\
if ! command -v bundle &> /dev/null; then\n\
    echo "ERROR: bundle command not found after rbenv setup"\n\
    echo "Attempting to install bundler..."\n\
    gem install bundler\n\
    rbenv rehash\n\
fi\n\
\n\
# Install dependencies if not already installed\n\
if [ ! -d "vendor/bundle" ] && [ -f "Gemfile" ]; then\n\
    echo "Installing Ruby dependencies..."\n\
    bundle install\n\
fi\n\
\n\
# Precompile assets if not already done\n\
if [ ! -d "public/assets" ]; then\n\
    echo "Precompiling Rails assets..."\n\
    bundle exec rails assets:precompile\n\
fi\n\
\n\
echo "Starting Rails server..."\n\
exec bundle exec rails server -b 0.0.0.0 -p 18080\n\
' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]
