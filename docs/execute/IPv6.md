Some scenarios requires the docker daemon to supports IPv6. They won;t start with this message if it's not activated :

```
_pytest.outcomes.Exit: IPv6 is not enabled on the docker daemon
```

## MacOS

Not yet supported at the current last version of Docker Desktop for Mac (4.36.0). See https://github.com/docker/for-mac/issues/1432

## Linux

Run this command

```bash
echo '{"ipv6": true, "fixed-cidr-v6": "2001:db8:1::/64"}' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
```


## Windows

TODO
