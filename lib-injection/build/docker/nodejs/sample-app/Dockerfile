FROM public.ecr.aws/docker/library/node:18

# Create app directory.
WORKDIR /usr/src/app

COPY . .

EXPOSE 18080
CMD [ "node", "index.js" ]
