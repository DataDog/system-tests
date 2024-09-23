FROM python:3.8-slim

ENV PYTHONUNBUFFERED 1
ENV DD_PROFILING_ENABLED true # profiling will crash the service on load if it does not pickup autoinjection correctly
WORKDIR /src
ADD . /src

RUN pip install -r requirements.txt

EXPOSE 18080
CMD ["python", "server.py"]
