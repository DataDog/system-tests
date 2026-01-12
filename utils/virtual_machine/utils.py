import json


def nginx_parser(nginx_config_file: str):
    """Parse the nginx config file and return the apps in the return block of the location block of the server block of the http block.
    TODO: Improve this uggly code
    """
    import crossplane

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
