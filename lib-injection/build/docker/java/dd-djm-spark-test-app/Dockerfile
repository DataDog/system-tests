FROM apache/spark:3.4.4

WORKDIR /opt/spark/work-dir

USER root
COPY launch.sh /opt/spark/work-dir/launch.sh
RUN chown spark:spark /opt/spark/work-dir/launch.sh
RUN chmod +x /opt/spark/work-dir/launch.sh
USER spark

CMD ["/opt/spark/work-dir/launch.sh"]
