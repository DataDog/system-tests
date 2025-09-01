FROM python:3.13-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl git gcc g++ make cmake

# print versions
RUN python --version && curl --version

# install python deps
ENV PIP_ROOT_USER_ACTION=ignore
RUN pip install --upgrade pip
RUN pip install django==5.2.4 pycryptodome==3.23.0 gunicorn==23.0.0 gevent==25.5.1 requests==2.32.4 boto3==1.34.141 'moto[ec2,s3,all]'==5.0.14 xmltodict==0.14.2


#8 27.23 Successfully installed Jinja2-3.1.6 MarkupSafe-3.0.2 PyYAML-6.0.2 annotated-types-0.7.0 antlr4-python3-runtime-4.13.2 asgiref-3.9.1 attrs-25.3.0 aws-sam-translator-1.99.0 aws-xray-sdk-2.14.0 boto3-1.34.141 botocore-1.34.162 certifi-2025.7.14 cffi-1.17.1 cfn-lint-1.38.0 charset_normalizer-3.4.2 cryptography-45.0.5 django-5.2.4 docker-7.1.0 gevent-25.5.1 graphql-core-3.2.6 greenlet-3.2.3 gunicorn-23.0.0 idna-3.10 jmespath-1.0.1 joserfc-1.2.2 jsondiff-2.2.1 jsonpatch-1.33 jsonpath-ng-1.7.0 jsonpointer-3.0.0 jsonschema-4.25.0 jsonschema-path-0.3.4 jsonschema-specifications-2025.4.1 lazy-object-proxy-1.11.0 moto-5.0.14 mpmath-1.3.0 multipart-1.2.1 networkx-3.5 openapi-schema-validator-0.6.3 openapi-spec-validator-0.7.2 packaging-25.0 pathable-0.4.4 ply-3.11 py-partiql-parser-0.5.6 pycparser-2.22 pycryptodome-3.23.0 pydantic-2.11.7 pydantic-core-2.33.2 pyparsing-3.2.3 python-dateutil-2.9.0.post0 referencing-0.36.2 regex-2024.11.6 requests-2.32.4 responses-0.25.7 rfc3339-validator-0.1.4 rpds-py-0.26.0 s3transfer-0.10.4 setuptools-80.9.0 six-1.17.0 sqlparse-0.5.3 sympy-1.14.0 typing-inspection-0.4.1 typing_extensions-4.14.1 urllib3-2.5.0 werkzeug-3.1.3 wrapt-1.17.2 xmltodict-0.14.2 zope.event-5.1.1 zope.interface-7.2
#8 DONE 30.1s

# Install Rust toolchain
RUN curl https://sh.rustup.rs -sSf | sh -s -- --default-toolchain stable -y
ENV PATH="/root/.cargo/bin:$PATH"

# docker build --progress=plain -f utils/build/docker/python/django-py3.13.base.Dockerfile -t datadog/system-tests:django-py3.13.base-v1 .
# docker push datadog/system-tests:django-py3.13.base-v1

