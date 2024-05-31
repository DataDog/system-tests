#!/bin/bash
echo "START RUN APP MicroVM"

cd /shared_volume
sed -i "s/18080/5985/g" index.js 
bash -c 'export DD_APM_INSTRUMENTATION_DEBUG=TRUE node index.js &'
echo "RUN DONE MicroVM"