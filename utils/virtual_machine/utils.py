from copy import copy


def get_tested_apps_vms(vm):
    """Workaround for multicontainer apps. We are going duplicate the machines for each runtime inside of docker compose.
    This means, if I have a multicontainer app with 3 containers (runtimes) running on 1 vm, I will have 3 machines with the same configuration but with different runtimes.
    NOTE: On AWS we only run 1 vm. We duplicate the vms for test isolation.
    """
    vms_by_runtime = []
    vms_by_runtime_ids = []
    deployed_weblog = vm.get_provision().get_deployed_weblog()
    if deployed_weblog.app_type == "multicontainer":
        for weblog in deployed_weblog.multicontainer_apps:
            vm_by_runtime = copy(vm)
            vm_by_runtime.set_deployed_weblog(weblog)
            vms_by_runtime.append(vm_by_runtime)
            vms_by_runtime_ids.append(vm_by_runtime.get_vm_unique_id())
    else:
        vms_by_runtime.append(vm)
        vms_by_runtime_ids.append(vm.get_vm_unique_id())

    return vms_by_runtime, vms_by_runtime_ids


def nginx_parser(nginx_config_file):
    """Parse the nginx config file and return the apps in the return block of the location block of the server block of the http block.
    TODO: Improve this uggly code
    """
    import crossplane
    import json

    nginx_config = crossplane.parse(nginx_config_file)
    config_endpoints = nginx_config["config"]
    for config_endpoint in config_endpoints:
        parsed_data = config_endpoint["parsed"]
        for parsed in parsed_data:
            if "http" == parsed["directive"]:
                parsed_blocks = parsed["block"]
                for parsed_block in parsed_blocks:
                    if "server" in parsed_block["directive"]:
                        parsed_server_blocks = parsed_block["block"]
                        for parsed_server_block in parsed_server_blocks:
                            if "location" in parsed_server_block["directive"] and parsed_server_block["args"][0] == "/":
                                parsed_server_location_blocks = parsed_server_block["block"]
                                for parsed_server_location_block in parsed_server_location_blocks:
                                    if "return" in parsed_server_location_block["directive"]:
                                        return_args = parsed_server_location_block["args"]
                                        # convert string to  object
                                        json_object = json.loads(return_args[1].replace("'", '"'))
                                        return json_object["apps"]
