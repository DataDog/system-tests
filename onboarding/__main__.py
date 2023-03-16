"""An AWS Python Pulumi program"""
import pulumi
import pulumi_aws as aws

import pulumi_command as command
import logging
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
logging.basicConfig(filename="pulumi.log", level=logging.INFO)  # TODO one log file for each vm


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


def remote_install(connection, command_identifier, install_info, depends_on, add_dd_keys=False):
    if add_dd_keys:
        command_exec = "DD_API_KEY=" + dd_api_key + " DD_SITE=" + dd_site + " " + install_info["command"]
    else:
        command_exec = install_info["command"]

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

    cmd_exec_install.stdout.apply(lambda outputlog: logging.info(outputlog))

    return cmd_exec_install


def build_local_weblog(ec2_name, weblog_instalations, depends):
    logging.info("Building weblog application: " + weblog_instalations["name"])
    if "local-script" in weblog_instalations:
        webapp_build = command.local.Command(
            "build-weblog_" + ec2_name,
            create="sh " + weblog_instalations["local-script"],
            opts=pulumi.ResourceOptions(depends_on=[depends]),
        )
        webapp_build.stdout.apply(lambda outputlog: logging.info(outputlog))
        return webapp_build
    else:
        return depends


def infraestructure_provision(provision_parser):
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
                        prepare_reos_installer = remote_install(
                            connection, "prepare-repos-installer_" + ec2_name, prepare_repos_install["install"], server
                        )

                        # Install agent
                        agent_installer = remote_install(
                            connection,
                            "agent-installer_" + ec2_name,
                            agent_instalations["install"],
                            prepare_reos_installer,
                            True,
                        )

                        # Install autoinjection
                        autoinjection_installer = remote_install(
                            connection,
                            "autoinjection-installer_" + ec2_name,
                            autoinjection_instalations["install"],
                            agent_installer,
                        )

                        # Install language variants
                        lang_variant_installer = remote_install(
                            connection,
                            "lang-variant-installer_" + ec2_name,
                            language_variants_instalations["install"],
                            autoinjection_installer,
                        )

                        # Build weblog app
                        webapp_build = build_local_weblog(ec2_name, weblog_instalations, lang_variant_installer)
                        weblog_runner = remote_install(
                            connection, "run-weblog_" + ec2_name, weblog_instalations["install"], webapp_build
                        )
                        pulumi.export("privateIp_" + ec2_name, server.private_ip)


provision_filter = load_filter()
provision_parser = Provision_parser(provision_filter)
infraestructure_provision(provision_parser)
