set -e 

docker build -f ./utils/interfaces/schemas/Dockerfile -t schemas-doc-server .
docker run -p 7070:80 schemas-doc-server