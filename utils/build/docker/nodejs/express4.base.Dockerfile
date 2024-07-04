FROM node:18-slim

RUN apt-get update && apt-get install -y jq curl git
