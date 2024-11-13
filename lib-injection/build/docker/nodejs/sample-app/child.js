console.log('Child process started');

setTimeout(() => {
  console.log('Child process exiting after 5 seconds');
  process.kill(process.pid, 'SIGSEGV');
}, 5000);
