console.log('Child process started');

setTimeout(() => {
  console.log('Child process exiting after 10 seconds');
  process.kill(process.pid, 'SIGSEGV');
}, 10000); // Add a delay before crashing otherwise the telemetry forwarder leaves a zombie behind
