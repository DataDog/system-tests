The `IPV6` scenario setup an IPv6 docker network and use an IPv6 address as DD_AGENT_HOST to verify that the library is able to communicate to the agent using an IPv6 address. It does not use a proxy between the lib and the agent to not interfer at any point here, so all assertions must be done on the outgoing traffic from the agent.

Please note that it requires the docker daemon to supports IPv6. It should be ok on Linux CI and Mac OS, but has not be tested on Windows.

A user has seen his network function altered after running it on a linux latptop (to be investigated). If it happen, `docker network prune` may sole the issue.
