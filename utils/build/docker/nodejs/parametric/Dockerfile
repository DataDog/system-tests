
FROM node:18.10-slim
RUN apt-get install -y git
WORKDIR /client
COPY ./package.json /client/
COPY ./package-lock.json /client/
COPY ./*.js /client/
COPY ./npm/* /client/
RUN npm install
RUN npm install dd-trace
