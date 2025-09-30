FROM public.ecr.aws/docker/library/node:18

# Create app directory
WORKDIR /usr/src/app

# Copy package files first for better Docker layer caching
COPY package*.json ./
COPY .npmrc ./

# Install dependencies with exact versions using npm ci
RUN npm ci --only=production --no-audit --no-fund

# Copy the rest of the application
COPY . .

EXPOSE 18080
CMD [ "node", "index.js" ]
