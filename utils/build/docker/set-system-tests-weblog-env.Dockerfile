FROM system_tests/weblog

# files for exotic scenarios
RUN echo "corrupted::data" > /appsec_corrupted_rules.yml

RUN chmod +x app.sh
CMD [ "./app.sh" ]
