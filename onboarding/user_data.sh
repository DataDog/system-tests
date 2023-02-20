#!/bin/bash

sudo apt-get update
sudo apt install -y openjdk-11-jre-headless

#Install agent and lib-injection dd software
DD_API_KEY=zzzzzzzzz DD_SITE="datadoghq.com" bash -c "$(curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script_agent7.sh)"
curl -s https://packagecloud.io/install/repositories/randomanderson/autoinject_test/script.deb.sh | os=any dist=any sudo -E bash
sudo apt-get install datadog-apm-inject datadog-apm-library-java

#Clone and compile weblog app
git clone https://github.com/DataDog/system-tests.git /home/ubuntu/system-tests
cd /home/ubuntu/system-tests/lib-injection/build/docker/java/dd-lib-java-init-test-app
./gradlew build

#Enable auto injection and Start app in new shell
#LD_PRELOAD is only going to affect new processes, not existing ones. We are instrumenting execve, which is invoked on process launch. If the shell was launched before the preload library was installed, then launching a new process with the old shell won’t run the instrumentation code.
dd-host-install
sudo bash -c 'DD_CONFIG_SOURCES=BASIC DD_INJECT_DEBUG=TRUE java -Dserver.port=7777 -jar /home/ubuntu/system-tests/lib-injection/build/docker/java/dd-lib-java-init-test-app/build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar >> /home/ubuntu/output.txt 2>&1'
