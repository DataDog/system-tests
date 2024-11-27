System tests spawn several services before starting. Here is the lifecycle:

1. Starts agent procy and library proxy
1. Starts runner => the runner will spy communication thanks to proxies, and will starts tests only when all components are up and running
1. Starts agent
1. Starts weblog
1. Execute tests
1. Exports all images logs
1. End of process
