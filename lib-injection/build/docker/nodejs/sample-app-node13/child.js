console.log('Child process started');

setTimeout(() => {
  console.log('Child process exiting after 5 seconds');
  // process.exit(0); // Exit the child process gracefully
  process.kill(process.pid, 'SIGSEGV');
}, 5000);

// process.kill(process.pid, 'SIGSEGV');