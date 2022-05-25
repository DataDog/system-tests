FROM python:3.9
WORKDIR /client
COPY requirements.txt .
RUN pip install -r requirements.txt
# ADD apm_test_client ./apm_test_client
# CMD ["python", "-m", "apm_test_client"]
CMD ["bash", "run.sh"]
