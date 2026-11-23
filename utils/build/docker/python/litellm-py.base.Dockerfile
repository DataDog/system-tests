FROM python:3.11-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl

WORKDIR /app

# The app uses pydantic and starlette directly, so they are pinned too.
RUN python -m pip install fastapi==0.100.0 starlette==0.27.0 pydantic==2.14.3 anyio==4.14.2 uvicorn==0.20.0 h11==0.16.0 \
    idna==3.19 py-spy==0.4.2
