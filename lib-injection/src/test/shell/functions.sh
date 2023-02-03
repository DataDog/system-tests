#!/bin/bash

# Exit early for any failed commands
set -e
# Print commands that are run
set -x

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
        kind create cluster --image=kindest/node:v1.25.3@sha256:f52781bc0d7a19fb6c405c2af83abfeb311f130707a0e219175677e366cc45d1 --name lib-injection-testing --config "${SRC_DIR}/test/resources/kind-config.yaml"
    fi
    kubectl wait --for=condition=Ready nodes --all --timeout=5m
}

function ensure-buildx() {
    if ! [[ "$(docker buildx ls)" =~ "lib-injection-testing" ]] ;  then
        docker buildx create --name lib-injection-testing
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
    helm install datadog --wait --set datadog.apiKey=${DD_API_KEY} --set datadog.appKey=${DD_APP_KEY} -f "${operator_file}" datadog/datadog 
    pod_name=$(kubectl get pods -l app=datadog-cluster-agent -o name)
    kubectl wait "${pod_name}" --for condition=ready --timeout=5m
    sleep 15 && kubectl get pods
}

function deploy-test-agent() {
    echo "[Deploy] deploy-test-agent"
    kubectl apply -f "${SRC_DIR}/test/resources/dd-apm-test-agent-config.yaml"
    kubectl rollout status daemonset/datadog --timeout=5m
    echo "[Deploy] Wait for test agent pod"
    kubectl wait --for=condition=ready pod -l app=datadog --timeout=5m
    kubectl get pods -l app=datadog
    echo "[Deploy] deploy-test-agent done"
}

function deploy-agents() {
    echo "[Deploy] deploy-agents"
    if [ ${USE_ADMISSION_CONTROLLER} -eq 1 ] ;  then
        echo "[Deploy] Using admission controller"
        deploy-operator
    fi
    deploy-test-agent
}

function reset-app() {
    kubectl delete pods my-app
}

function deploy-app() {
    app_name=my-app
    echo "[Deploy] deploy-app: ${app_name} . Using UDS: ${USE_UDS}. Using adm.controller: ${USE_ADMISSION_CONTROLLER}"
    [[ $TEST_LIBRARY = nodejs ]] && library=js || library=$TEST_LIBRARY
    echo "[Deploy] Using library alias: ${library}"

    helm template lib-injection/common \
      -f "lib-injection/build/docker/$TEST_LIBRARY/values-override.yaml" \
      --set library="${library}" \
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

function test-for-traces() {
    echo "[Test] test for traces"

    tmpfile=$(mktemp -t traces.XXXXXX)
    echo "tmp file in ${tmpfile}"

    wget -O $(readlink -f "${tmpfile}") http://localhost:18126/test/traces || true
    traces=`cat ${tmpfile}`
    echo "[Test] ${traces}"
    if [[ ${#traces} -lt 3 ]] ; then
        echoerr "No traces reported - ${traces}"
        print-debug-info
        reset-all
        exit 1
    else
        count=`jq '. | length' <<< "${traces}"`
        echo "Received ${count} traces so far"
    fi
    
    print-debug-info
    echo "[Test] test-for traces completed successfully"
    reset-all
}

function print-debug-info(){
    log_dir=${BASE_DIR}/../logs_lib-injection/
    mkdir -p ${log_dir}/pod
    echo "[debug] Generating debug log files... (${log_dir})"
    echo "[debug] Export: Current cluster status"
    kubectl get pods > "${log_dir}/cluster_pods.log"
    kubectl get deployments datadog-cluster-agent > "${log_dir}/cluster_deployments.log" || true
 
    echo "[debug] Export: Describe my-app status"
    kubectl describe pod my-app > "${log_dir}/my-app_describe.log"
    kubectl logs pod/my-app > "${log_dir}/my-app.log"

    echo "[debug] Export: Daemonset logs"
    kubectl logs daemonset/datadog > "${log_dir}/daemonset_datadog.log"

    if [ ${USE_ADMISSION_CONTROLLER} -eq 1 ] ;  then 

        pod_cluster_name=$(kubectl get pods -l app=datadog-cluster-agent -o name)

        echo "[debug] Export: Describe datadog-cluster-agent"
        kubectl describe ${pod_cluster_name} > "${log_dir}/${pod_cluster_name}_describe.log"
        kubectl logs ${pod_cluster_name} > "${log_dir}/${pod_cluster_name}.log"

        echo "[debug] Export: Telemetry datadog-cluster-agent"
        kubectl exec -it ${pod_cluster_name} -- agent telemetry > "${log_dir}/${pod_cluster_name}_telemetry.log"

        echo "[debug] Export: Status datadog-cluster-agent"
        # Sometimes this command fails.Ignoring this error
        kubectl exec -it ${pod_cluster_name} -- agent status > "${log_dir}/${pod_cluster_name}_status.log" || true
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
