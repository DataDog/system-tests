from EC2_manager import *
import pytest
    
def pytest_sessionstart(session):
    print("Test session start")
    ec2Manager = EC2Manager()
    pytest.instance_id=ec2Manager.create_EC2_instance()
    pytest.public_ip=ec2Manager.get_public_ip(pytest.instance_id)
    print(pytest.public_ip)
    print("Waiting for weblog available")
    wait_for_port(7777,pytest.public_ip,220.0)
    print("Weblog app is ready!!!!!!")

def pytest_sessionfinish(session, exitstatus):
    print("Stopping instances")
    ec2Manager = EC2Manager()
    ec2Manager.stop_instance(pytest.instance_id)
    print("Done!")
