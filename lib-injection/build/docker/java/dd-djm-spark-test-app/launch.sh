#!/bin/bash

if [ -z "${LIB_INIT_IMAGE}" ]; then
    echo "LIB_INIT_IMAGE is not set"
    exit 1
else
    echo "LIB_INIT_IMAGE is set to ${LIB_INIT_IMAGE}"
fi

if [ -z "${AUTO_INJECT_VERSION}" ]; then
    echo "AUTO_INJECT_VERSION is not set, default to latest"
    AUTO_INJECT_VERSION="latest" # default to latest for now.
else
    echo "AUTO_INJECT_VERSION is set to ${AUTO_INJECT_VERSION}"
fi

# Submit a example spark job with DJM enabled
$SPARK_HOME/bin/spark-submit   \
--class org.apache.spark.examples.SparkPi  \
 --master k8s://https://$KUBERNETES_SERVICE_HOST:$KUBERNETES_SERVICE_PORT   \
 --conf spark.kubernetes.container.image=apache/spark:3.4.4  \
 --deploy-mode cluster  \
 --conf spark.kubernetes.namespace=default   \
 --conf spark.kubernetes.executor.deleteOnTermination=false   \
 --conf spark.kubernetes.driver.label.admission.datadoghq.com/enabled=true   \
 --conf spark.kubernetes.authenticate.driver.serviceAccountName=spark   \
 --conf spark.kubernetes.authenticate.executor.serviceAccountName=spark   \
 --conf spark.kubernetes.driver.annotation.admission.datadoghq.com/java-lib.custom-image=${LIB_INIT_IMAGE} \
 --conf spark.kubernetes.driverEnv.DD_APM_INSTRUMENTATION_DEBUG=true   \
 --conf spark.kubernetes.driver.annotation.admission.datadoghq.com/apm-inject.version=${AUTO_INJECT_VERSION}   \
 --conf spark.driver.extraJavaOptions="-Ddd.integrations.enabled=false -Ddd.data.jobs.enabled=true -Ddd.service=spark-pi-example -Ddd.env=test -Ddd.version=0.1.0 -Ddd.tags=team:djm" \
 --conf spark.kubernetes.driverEnv.HADOOP_HOME=/opt/hadoop/  \
 local:///opt/spark/examples/jars/spark-examples.jar 20

# start a long running server to keep the web-log up.
python3 -m http.server ${SERVER_PORT:-18080}