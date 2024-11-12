FROM system_tests/weblog

ARG SYSTEM_TESTS_LIBRARY
ENV SYSTEM_TESTS_LIBRARY=$SYSTEM_TESTS_LIBRARY

ARG SYSTEM_TESTS_WEBLOG_VARIANT
ENV SYSTEM_TESTS_WEBLOG_VARIANT=$SYSTEM_TESTS_WEBLOG_VARIANT

# files for exotic scenarios
RUN echo "corrupted::data" > /appsec_corrupted_rules.yml

RUN chmod +x app.sh
CMD [ "./app.sh" ]
