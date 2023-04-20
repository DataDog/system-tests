"""An AWS Python Pulumi program"""
import pulumi
import pulumi_aws as aws
import pulumi_command as command
from pulumi import Output

import logging
import logging.config
import os
from provision_filter import Provision_filter
from provision_parser import Provision_parser


config_infra = pulumi.Config("ddinfra")
config_agent = pulumi.Config("ddagent")


# Load AWS Configuration
keyName = config_infra.get("aws/defaultKeyPairName")
subnet_id = config_infra.get("aws/subnet_id")
vpc_security_group_ids = config_infra.get("aws/vpc_security_group_ids").split(",")
privateKeyPath = config_infra.get("aws/defaultPrivateKeyPath")
instance_type = config_infra.get("aws/instance_type")

# Load DD agent Configuration
dd_api_key = config_agent.require("apiKey")
dd_app_key = config_agent.require("appKey")
dd_site = config_agent.require("site")


private_key_pem = (lambda path: open(path).read())(privateKeyPath)
# logging.config.fileConfig("logging.conf")
formatter = logging.Formatter("%(message)s")


def pulumi_logger(log_name, level=logging.INFO):
    handler = logging.FileHandler(f"logs/{log_name}.log")
    handler.setFormatter(formatter)
    specified_logger = logging.getLogger(log_name)
    specified_logger.setLevel(level)
    specified_logger.addHandler(handler)
    return specified_logger


def load_filter():
    config_filter = pulumi.Config("ddfilter")
    provision_scenario = config_filter.get("provision_scenario")
    language = config_filter.get("language")
    env = config_filter.get("env")
    os_distro = config_filter.get("os_distro")
    weblog = config_filter.get("weblog")
    print(f"Filter-> Provision scenario:", provision_scenario)
    print(f"Filter-> Language:", language)
    print(f"Filter-> Autoinjection env:", env)
    print(f"Filter-> OS distro:", os_distro)
    print(f"Filter-> weblog:", weblog)

    return Provision_filter(provision_scenario, language, env, os_distro, weblog)


def remote_install(connection, command_identifier, install_info, depends_on, add_dd_keys=False, logger_name=None):
    #Do we need to add env variables?
    if install_info is None:
        return depends_on
    if add_dd_keys:
        command_exec = "DD_API_KEY=" + dd_api_key + " DD_SITE=" + dd_site + " " + install_info["command"]
    else:
        command_exec = install_info["command"]
        
    #Execute local script if we need
    if "local-script" in install_info:
        webapp_build = command.local.Command(
            "local-script_" + command_identifier,
            create="sh " + install_info["local-script"],
            opts=pulumi.ResourceOptions(depends_on=[depends_on]),
        )
        webapp_build.stdout.apply(
            lambda outputlog: pulumi_logger("build_local_weblogs").info(outputlog)
        )
        depends_on = webapp_build
        
    #Copy files from local to remote if we need
    if "copy_files" in install_info:
        for file_to_copy in install_info["copy_files"]:
            cmd_cp_webapp = command.remote.CopyFile(
                file_to_copy["name"] + "-" + command_identifier,
                connection=connection,
                local_path=file_to_copy["local_path"],
                remote_path=file_to_copy["remote_path"],
                opts=pulumi.ResourceOptions(depends_on=[depends_on]),
            )
        depends_on = cmd_cp_webapp

    # Execute a basic command on our server.
    cmd_exec_install = command.remote.Command(
        command_identifier,
        connection=connection,
        create=command_exec,
        opts=pulumi.ResourceOptions(depends_on=[depends_on]),
    )
    if logger_name:
        cmd_exec_install.stdout.apply(lambda outputlog: pulumi_logger(logger_name).info(outputlog))
    else:
        Output.all(connection.host, cmd_exec_install.stdout).apply(lambda args: pulumi_logger(args[0]).info(args[1]))

    return cmd_exec_install

def infraestructure_provision(provision_filter):
    provision_parser = Provision_parser(provision_filter)
    for ec2_data in provision_parser.ec2_instances_data():
        os_type = ec2_data["os_type"]
        os_distro = ec2_data["os_distro"]
        os_branch = ec2_data.get("os_branch", None)

        # for every different agent instalation
        for agent_instalations in provision_parser.ec2_agent_install_data(os_type, os_distro, os_branch):
            # for every different autoinjection software (by language, by os and by env)
            for autoinjection_instalations in provision_parser.ec2_autoinjection_install_data(
                os_type, os_distro, os_branch
            ):
                language = autoinjection_instalations["language"]
                # for every different language variants
                for language_variants_instalations in provision_parser.ec2_language_variants_install_data(
                    language, os_type, os_distro, os_branch
                ):
                    # for every weblog supported for every language variant
                    for weblog_instalations in provision_parser.ec2_weblogs_install_data(
                        language, language_variants_instalations["version"], os_type, os_distro, os_branch
                    ):
                        ec2_name = (
                            ec2_data["name"]
                            + "__agent-"
                            + agent_instalations["env"]
                            + "__autoinjection-"
                            + language
                            + "-"
                            + autoinjection_instalations["env"]
                            + "__lang-variant-"
                            + language_variants_instalations["name"]
                            + "__weblog-"
                            + weblog_instalations["name"]
                        )

                        server = aws.ec2.Instance(
                            ec2_name,
                            instance_type=instance_type,
                            vpc_security_group_ids=vpc_security_group_ids,
                            subnet_id=subnet_id,
                            key_name=keyName,
                            ami=ec2_data["ami_id"],
                            tags={"Name": ec2_name,},
                        )

                        connection = command.remote.ConnectionArgs(
                            host=server.private_ip,
                            user=ec2_data["user"],
                            private_key=private_key_pem,
                            dial_error_limit=-1,
                        )

                        # Prepare repositories
                        prepare_repos_install = provision_parser.ec2_prepare_repos_install_data(os_type, os_distro)
                        prepare_repos_installer = remote_install(
                            connection, "prepare-repos-installer_" + ec2_name, prepare_repos_install["install"], server
                        )

                        # Prepare docker installation if we need
                        prepare_docker_install = provision_parser.ec2_prepare_docker_install_data(os_type, os_distro)
                        prepare_docker_installer = remote_install(
                            connection,
                            "prepare-docker-installer_" + ec2_name,
                            prepare_docker_install["install"],
                            prepare_repos_installer,
                        )

                        # Install agent
                        agent_installer = remote_install(
                            connection,
                            "agent-installer_" + ec2_name,
                            agent_instalations["install"],
                            prepare_docker_installer,
                            add_dd_keys=True,
                        )
                        
                        pulumi.export(
                            "privateIp_" + provision_filter.provision_scenario + "__" + ec2_name, server.private_ip
                        )
                        
                        # Install autoinjection
                        autoinjection_installer = remote_install(
                            connection,
                            "autoinjection-installer_" + ec2_name,
                            autoinjection_instalations["install"],
                            agent_installer,
                        )

                        # Extract installed component versions
                        installation_check_data = provision_parser.ec2_installation_checks_data(
                            language, os_type, os_distro, os_branch
                        )
                        remote_install(
                            connection,
                            "installation-check_" + ec2_name,
                            installation_check_data["install"],
                            autoinjection_installer,
                            logger_name="pulumi_installed_versions",
                        )

                        # Install language variants
                        lang_variant_installer = remote_install(
                            connection,
                            "lang-variant-installer_" + ec2_name,
                            language_variants_instalations["install"],
                            autoinjection_installer,
                        )

                        # Build weblog app
                       # webapp_build = build_local_weblog(ec2_name, weblog_instalations, lang_variant_installer)
                        weblog_runner = remote_install(
                            connection,
                            "run-weblog_" + ec2_name,
                            weblog_instalations["install"],
                          #  webapp_build,
                            lang_variant_installer,
                            add_dd_keys=True,
                        )




provision_filter = load_filter()

infraestructure_provision(provision_filter)
