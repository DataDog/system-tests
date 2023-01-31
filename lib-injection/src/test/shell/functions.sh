#!/bin/bash

## HELPERS
function echoerr() {
    echo "$@" 1>&2;
}
## end HELPERS

if [ -z "${BASE_DIR}" ] ; then
    echoerr "MUST define BASE_DIR before sourcing this file"
    exit 1
fi
if [ -z "${TEST_LIBRARY}" ] ; then
    echoerr "MUST define TEST_LIBRARY before sourcing this file"
    exit 1
fi

if [ -z "${WEBLOG_VARIANT}" ] ; then
    echoerr "You should define WEBLOG_VARIANT before sourcing this file"
fi

if [ -z "${DOCKER_REGISTRY_IMAGES_PATH}" ] ; then
    echoerr "MUST define DOCKER_REGISTRY_IMAGES_PATH. For example: ghcr.io/datadog"
    exit 1
fi

if [ -z "${DOCKER_IMAGE_TAG}" ] ; then
    echo "DOCKER_IMAGE_TAG environment variable is not defined. Using default tag:local"
    export DOCKER_IMAGE_TAG=local
fi

if [ -z "${DOCKER_IMAGE_WEBLOG_TAG}" ] ; then
    echo "DOCKER_IMAGE_WEBLOG_TAG environment variable is not defined. Using value of variable DOCKER_IMAGE_TAG:[${DOCKER_IMAGE_TAG}] "
    export DOCKER_IMAGE_WEBLOG_TAG=$DOCKER_IMAGE_TAG
fi

if [ -z "${DD_API_KEY}" ] ; then
    echo "MOCK API KEY"
    export DD_API_KEY=apikey
    export DD_APP_KEY=appkey
fi

#TODO: homogenize the names of things. nodejs or js? python or py? Source of problems!!!!
 [[ $TEST_LIBRARY = nodejs ]] && init_image_repo_alias=js || init_image_repo_alias=$TEST_LIBRARY
 [[ $init_image_repo_alias = python ]] && init_image_repo_alias=py
 [[ $TEST_LIBRARY = nodejs ]] && init_image_alias=js || init_image_alias=$TEST_LIBRARY


if [ "$DOCKER_IMAGE_TAG" == "latest" ]; then
    #Release version are published in docker.io
    export INIT_DOCKER_IMAGE_REPO=docker.io/datadog/dd-lib-${init_image_alias}-init
elif [ "$DOCKER_IMAGE_TAG" == "local" ]; then
    #Docker hub doesn't allow multi level repo paths
    export INIT_DOCKER_IMAGE_REPO=${DOCKER_REGISTRY_IMAGES_PATH}/dd-lib-${init_image_alias}-init
else
    export INIT_DOCKER_IMAGE_REPO=${DOCKER_REGISTRY_IMAGES_PATH}/dd-trace-${init_image_repo_alias}/dd-lib-${init_image_alias}-init
fi

export APP_DOCKER_IMAGE_REPO=${DOCKER_REGISTRY_IMAGES_PATH}/system-tests/${WEBLOG_VARIANT}

if [ "$DOCKER_IMAGE_WEBLOG_TAG" == "local" ]; then
    #Docker hub doesn't allow multi level repo paths
    export APP_DOCKER_IMAGE_REPO=${DOCKER_REGISTRY_IMAGES_PATH}/${WEBLOG_VARIANT}
fi

export LIBRARY_INJECTION_INIT_IMAGE=${INIT_DOCKER_IMAGE_REPO}:${DOCKER_IMAGE_TAG}
export LIBRARY_INJECTION_TEST_APP_IMAGE=${APP_DOCKER_IMAGE_REPO}:${DOCKER_IMAGE_WEBLOG_TAG}
export SRC_DIR=${BASE_DIR}/src
export LIBRARY_DIR=${BASE_DIR}/${TEST_LIBRARY}

echo "------------------------------------------------------------------------"
printf '%s\t%s\n' "Library test dir:" "${LIBRARY_DIR}" \
                  "Test library:" "${TEST_LIBRARY}" \
                  "Weblog variant:" "${WEBLOG_VARIANT}" \
                  "Src dir:" "${SRC_DIR}" \
                  "Init image name: " "${LIBRARY_INJECTION_INIT_IMAGE}" \
                  "Test app image: " "${LIBRARY_INJECTION_TEST_APP_IMAGE}" |
  expand -t 20
echo "------------------------------------------------------------------------"

export USE_ADMISSION_CONTROLLER=0
export USE_UDS=0

## MODIFIERS
function uds() {
    export USE_UDS=1
}

function network() {
    export USE_UDS=0
}

function use-admission-controller() {
    export USE_ADMISSION_CONTROLLER=1
}

## FUNCTIONS
function reset-cluster() {
    if [[ "$(kind get clusters)" =~ "lib-injection-testing" ]] ;  then
        kind delete cluster --name lib-injection-testing
    fi
}

function reset-buildx() {
    if [[ "$(docker buildx ls)" =~ "lib-injection-testing" ]] ;  then
        echo "deleting docker buildx builder: lib-injection-testing"
        docker buildx rm lib-injection-testing
    fi
}

function reset-deploys() {
    reset-app
    helm uninstall datadog
    kubectl delete daemonset datadog
    kubectl delete pods -l app=datadog
}

function reset-all() {
    reset-cluster
    reset-buildx
}

function ensure-cluster() {
    if ! [[ "$(kind get clusters)" =~ "lib-injection-testing" ]] ;  then
        kind create cluster --image=kindest/node:v1.22.9 --name lib-injection-testing --config "${SRC_DIR}/test/resources/kind-config.yaml" || exit 1
    fi
}

function ensure-buildx() {
    if ! [[ "$(docker buildx ls)" =~ "lib-injection-testing" ]] ;  then
        docker buildx create --name lib-injection-testing || exit 1
    fi
    docker buildx use lib-injection-testing
}

function deploy-operator() {
    operator_file=${BASE_DIR}/common/operator-helm-values.yaml
    if [ ${USE_UDS} -eq 1 ] ; then
      echo "[Deploy operator] Using UDS"  
      operator_file=${BASE_DIR}/common/operator-helm-values-uds.yaml
    fi
    echo "[Deploy operator] Configuring helm repository"
    helm repo add datadog https://helm.datadoghq.com
    helm repo update

    echo "[Deploy operator] helm install datadog with config file [${operator_file}]"
    helm install datadog --set datadog.apiKey=${DD_API_KEY} --set datadog.appKey=${DD_APP_KEY} -f "${operator_file}" datadog/datadog
    
    sleep 15 && kubectl get pods

    pod_name=$(kubectl get pods -l app=datadog-cluster-agent -o name)
    kubectl wait "${pod_name}" --for condition=ready --timeout=5m
    sleep 15 && kubectl get pods
}

function deploy-operator-auto() {
    echo "[Deploy operator] Using Patcher"
    operator_file=${BASE_DIR}/common/operator-helm-values-auto.yaml

    echo "[Deploy operator] Configuring helm repository"
    helm repo add datadog https://helm.datadoghq.com
    helm repo update

    echo "[Deploy operator] helm install datadog with config file [${operator_file}]"
    helm install datadog --set datadog.apiKey=${DD_API_KEY} --set datadog.appKey=${DD_APP_KEY} -f "${operator_file}" datadog/datadog
    
    # TODO: This is a hack until the patching permission is added in the official helm chart.
    echo "[Deploy operator] adding patch permissions to the datadog-cluster-agent clusterrole"
    kubectl patch clusterrole datadog-cluster-agent --type='json' -p '[{"op": "add", "path": "/rules/0", "value":{ "apiGroups": ["apps"], "resources": ["deployments"], "verbs": ["patch"]}}]'
   
    sleep 15 && kubectl get pods

    pod_name=$(kubectl get pods -l app=datadog-cluster-agent -o name)
    kubectl wait "${pod_name}" --for condition=ready --timeout=5m
    sleep 15 && kubectl get pods
}

function deploy-test-agent() {
    echo "[Deploy] deploy-test-agent"
    kubectl apply -f "${SRC_DIR}/test/resources/dd-apm-test-agent-config.yaml"
    kubectl rollout status daemonset/datadog

    echo "[Deploy] Get pods"
    sleep 15 && kubectl get pods -l app=datadog

    pod_name=$(kubectl get pods -l app=datadog -o name)

    echo "[Deploy] pod_name: ${pod_name} waiting"
    kubectl wait "${pod_name}" --for condition=ready
    sleep 15 && kubectl get pods -l app=datadog
    echo "[Deploy] deploy-test-agent done"
}

function deploy-agents-manual() {
    echo "[Deploy] deploy-agents"
    deploy-test-agent
    if [ ${USE_ADMISSION_CONTROLLER} -eq 1 ] ;  then
        echo "[Deploy] Using admission controller"
        deploy-operator
    fi
}

function deploy-agents-auto() {
    echo "[Deploy] deploy-agents"
    deploy-test-agent
    echo "[Deploy] Cluster Agent with patcher enabled"
    deploy-operator-auto
    sleep 30
}

function reset-app() {
    kubectl delete pods my-app
}

function trigger-config-auto() {
    echo "[Auto Config] Triggering config change"
    config_name="${CONFIG_NAME:-config}"
    kubectl apply -f ${BASE_DIR}/build/docker/${TEST_LIBRARY}/${config_name}.yaml
    echo "[Auto Config] Waiting on the cluster agent to pick up the changes"
    sleep 90
    echo "[Auto Config] trigger-config-auto: waiting for deployments/test-${TEST_LIBRARY}-deployment available"
    kubectl wait deployments/test-${TEST_LIBRARY}-deployment --for condition=Available=True --timeout=5m
    kubectl get pods
    echo "[Auto Config] trigger-config-auto: done"
}

function deploy-app-manual() {
    app_name=my-app
    echo "[Deploy] deploy-app: ${app_name} . Using UDS: ${USE_UDS}. Using adm.controller: ${USE_ADMISSION_CONTROLLER}"
    [[ $TEST_LIBRARY = nodejs ]] && library=js || library=$TEST_LIBRARY
    echo "[Deploy] Using library alias: ${library}"

    helm template lib-injection/common \
      -f "lib-injection/build/docker/$TEST_LIBRARY/values-override.yaml" \
      --set library="${library}" \
      --set as_pod="true" \
      --set app=${app_name} \
      --set use_uds=${USE_UDS} \
      --set use_admission_controller=${USE_ADMISSION_CONTROLLER} \
      --set test_app_image="${LIBRARY_INJECTION_TEST_APP_IMAGE}" \
      --set init_image="${LIBRARY_INJECTION_INIT_IMAGE}" \
       | kubectl apply -f -
    echo "[Deploy] deploy-app: waiting for pod/${app_name} ready"
    kubectl wait pod/${app_name} --for condition=ready --timeout=5m
    sleep 5 && kubectl get pods
    echo "[Deploy] deploy-app done"
}

function deploy-app-auto() {
    echo "[Deploy] deploy-app-auto: deploying app for library ${TEST_LIBRARY}"

    deployment_name=test-${TEST_LIBRARY}-deployment
    helm template lib-injection/common \
      -f "lib-injection/build/docker/$TEST_LIBRARY/values-override.yaml" \
      --set library="${TEST_LIBRARY}" \
      --set as_deployment="true" \
      --set deployment=${deployment_name} \
      --set test_app_image="${LIBRARY_INJECTION_TEST_APP_IMAGE}" \
       | kubectl apply -f -

    echo "[Deploy] deploy-app-auto: waiting for deployments/${deployment_name} available"
    kubectl wait deployments/${deployment_name} --for condition=Available=True --timeout=5m
    sleep 5 && kubectl get pods

    echo "[Deploy] deploy-app-auto: done"
}

function trigger-app-rolling-update() {
    echo "[Deploy] trigger-app-rolling-update: updating deployment app ${TEST_LIBRARY}"

    deployment_name=test-${TEST_LIBRARY}-deployment
    kubectl set env deploy deployment_name ENV_FOO=ENV_BAR

    echo "[Deploy] trigger-app-rolling-update: waiting for deployments/${deployment_name} available"
    kubectl wait deployments/${deployment_name} --for condition=Available=True --timeout=5m
    sleep 15 && kubectl get pods

    echo "[Deploy] trigger-app-rolling-update: done"
}

function cleanup-auto() {
    echo "[Cleanup] delete deployments/${deployment_name}"
    deployment_name=test-${TEST_LIBRARY}-deployment
    kubectl delete deployments/${deployment_name}

    echo "[Cleanup] uninstall datadog helm chart"
    helm uninstall datadog

    echo "[Cleanup] delete test agent"
    kubectl delete daemonset datadog
}

function check-for-env-vars() {
    pod=$(kubectl get pods -l app=${TEST_LIBRARY}-app -o name)
    echo "[Test] test for env vars ${pod}"
    trace_sample_rate="0.90"
    if [ ${CONFIG_NAME} == "config-1" ] ;  then
        trace_sample_rate="0.50"
    fi
    # TODO: extend the list of tested env vars
    kubectl get ${pod} -oyaml | grep -A1 DD_TRACE_SAMPLE_RATE | grep ${trace_sample_rate}
}

function test-for-traces-manual() {
    echo "[Test] test for traces"

    tmpfile=$(mktemp -t traces.XXXXXX)
    echo "tmp file in ${tmpfile}"

    wget -O $(readlink -f "${tmpfile}") http://localhost:18126/test/traces || true
    traces=`cat ${tmpfile}`
    echo "[Test] ${traces}"
    if [[ ${#traces} -lt 3 ]] ; then
        echoerr "No traces reported - ${traces}"
        print-debug-info-manual
        reset-all
        exit 1
    else
        count=`jq '. | length' <<< "${traces}"`
        echo "Received ${count} traces so far"
    fi
    print-debug-info-manual
    echo "[Test] test-for traces completed successfully"
    reset-all
}

function test-for-traces-auto() {
    echo "[Test] test for traces"

    tmpfile=$(mktemp -t traces.XXXXXX)
    echo "tmp file in ${tmpfile}"

    wget -O $(readlink -f "${tmpfile}") http://localhost:18126/test/traces || true
    traces=`cat ${tmpfile}`
    echo "[Test] ${traces}"
    if [[ ${#traces} -lt 3 ]] ; then
        echoerr "No traces reported - ${traces}"
        print-debug-info-auto
        reset-all
        exit 1
    else
        count=`jq '. | length' <<< "${traces}"`
        echo "Received ${count} traces so far"
    fi
    print-debug-info-auto
    echo "[Test] test-for-traces completed successfully"
}

function print-debug-info-auto() {
    log_dir=${BASE_DIR}/../logs_lib-injection/
    mkdir -p ${log_dir}/pod
    echo "[debug] Generating debug log files... (${log_dir})"
    echo "[debug] Export: Current cluster status"
    kubectl get pods > ${log_dir}/cluster_pods.log
    kubectl get deployments datadog-cluster-agent > ${log_dir}/cluster_deployments.log

    echo "[debug] Export: Daemonset logs"
    kubectl logs daemonset/datadog > ${log_dir}/daemonset_datadog.log

    echo "[debug] Library deployment yaml and pod logs"
    kubectl get deploy test-${TEST_LIBRARY}-deployment -oyaml > ${log_dir}/test-${TEST_LIBRARY}-deployment.yaml
    kubectl get pods -l app=${TEST_LIBRARY}-app
    pod=$(kubectl get pods -l app=${TEST_LIBRARY}-app -o name)
    kubectl get po ${pod} -oyaml > ${log_dir}/${pod}.yaml
    kubectl logs ${pod} > ${log_dir}/${pod}.log

    echo "[debug] Cluster agent logs"
    pod_cluster_name=$(kubectl get pods -l app=datadog-cluster-agent -o name)
    kubectl logs ${pod_cluster_name} > ${log_dir}/${pod_cluster_name}.log
}

function print-debug-info-manual(){
    log_dir=${BASE_DIR}/../logs_lib-injection/
    mkdir -p ${log_dir}/pod
    echo "[debug] Generating debug log files... (${log_dir})"
    echo "[debug] Export: Current cluster status"
    kubectl get pods > ${log_dir}/cluster_pods.log
    kubectl get deployments datadog-cluster-agent > ${log_dir}/cluster_deployments.log

    echo "[debug] Export: Describe my-app status"
    kubectl describe pod my-app > ${log_dir}/my-app_describe.log
    kubectl logs pod/my-app > ${log_dir}/my-app.log

    echo "[debug] Export: Daemonset logs"
    kubectl logs daemonset/datadog > ${log_dir}/daemonset_datadog.log

    if [ ${USE_ADMISSION_CONTROLLER} -eq 1 ] ;  then 
        pod_cluster_name=$(kubectl get pods -l app=datadog-cluster-agent -o name)

        echo "[debug] Export: Describe datadog-cluster-agent"
        kubectl describe ${pod_cluster_name} > ${log_dir}/${pod_cluster_name}_describe.log
        kubectl logs ${pod_cluster_name} > ${log_dir}/${pod_cluster_name}.log

        echo "[debug] Export: Telemetry datadog-cluster-agent"
        kubectl exec -it ${pod_cluster_name} -- agent telemetry > ${log_dir}/${pod_cluster_name}_telemetry.log

        echo "[debug] Export: Status datadog-cluster-agent"
        #Sometimes this command fails.Ignoring this error
        kubectl exec -it ${pod_cluster_name} -- agent status > ${log_dir}/${pod_cluster_name}_status.log || true
    fi
}

function build-and-push-test-app-image() { 
    current_dir=$(pwd)
    cd lib-injection/build/docker/$TEST_LIBRARY/$WEBLOG_VARIANT
    ./build.sh
    cd $current_dir
}

#Used only to local testing
function build-and-push-init-image() {
    ensure-buildx

    if [ -z "${BUILDX_PLATFORMS}" ] ; then
        BUILDX_PLATFORMS=`docker buildx imagetools inspect --raw busybox:latest | jq -r 'reduce (.manifests[] | [ .platform.os, .platform.architecture, .platform.variant ] | join("/") | sub("\\/$"; "")) as $item (""; . + "," + $item)' | sed 's/,//'`
    fi

    echo "Installing tracer"
    sh $(pwd)/lib-injection/build/docker/${TEST_LIBRARY}/install_ddtrace.sh $(pwd)/binaries

    #TODO change this. Two options: 1) not build the image, pull it (best option). 2) change to main branch
    echo "Building init image"  
    echo "docker buildx build https://github.com/DataDog/dd-trace-${init_image_repo_alias}.git#robertomonteromiguel/lib_injection_system_tests_integration:lib-injection --build-context ${TEST_LIBRARY}_agent=$(pwd)/binaries/ --platform ${BUILDX_PLATFORMS} -t "${INIT_DOCKER_IMAGE_REPO}:${DOCKER_IMAGE_TAG}" --push "
    docker buildx build https://github.com/DataDog/dd-trace-${init_image_repo_alias}.git#robertomonteromiguel/lib_injection_system_tests_integration:lib-injection --build-context ${TEST_LIBRARY}_agent=$(pwd)/binaries/ --platform ${BUILDX_PLATFORMS} -t "${INIT_DOCKER_IMAGE_REPO}:${DOCKER_IMAGE_TAG}" --push
   
}
