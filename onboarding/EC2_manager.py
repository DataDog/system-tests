import boto3
from wait_for_tcp_port import *
from weblog_interface import *
from backend_interface import *

ec2_client = boto3.client('ec2', region_name='us-east-1')
ec2 = boto3.resource('ec2')

class EC2Manager:
        
    def list_EC2_instances(self):
        
        for instance in ec2.instances.all():
            print(
                "Id: {0}\nPlatform: {1}\nType: {2}\nPublic IPv4: {3}\nAMI: {4}\nState: {5}\n".format(
                instance.id, instance.platform, instance.instance_type, instance.public_ip_address, instance.image.id, instance.state
                )
            )
            
    def create_EC2_instance(self):
       # ami-0557a15b87f6559cf --> UBUNTU
       # system_tests_security_group
        
        text_file = open("user_data.sh", "r") 
        user_data = text_file.read()
        text_file.close()
        
        response = ec2_client.run_instances(
            BlockDeviceMappings=[
                {
                    'DeviceName': '/dev/xvda',
                    'Ebs': {

                        'DeleteOnTermination': True,
                        'VolumeSize': 15,
                        'VolumeType': 'gp2'
                    },
                },
            ],
            KeyName="robertomonteromiguel3",
            ImageId='ami-0557a15b87f6559cf',
            InstanceType='t3.small',
            MaxCount=1,
            MinCount=1,
            Monitoring={
                'Enabled': False
            },
            SecurityGroupIds=[
                'sg-043c9cf2fbc042260',
            ],
            UserData=user_data #you can see the user data logs in the path of instance: /var/log/cloud-init.log and /var/log/cloud-init-output.log
        )
        instanceId = response["Instances"][0]["InstanceId"];
        print(f"Instnce created ",instanceId) 
        return instanceId
        
    def stop_instance(self, instance):
        instances = [instance]
        ec2_client.stop_instances(InstanceIds=instances) 
        
    def get_public_ip(self, instance_id):
        # Get information for all running instances
        running_instances = ec2.instances.filter(Filters=[{
            'Name': 'instance-id',
            'Values': [instance_id]}])
        print(running_instances)
        for instance in running_instances:
            print(f"waiting for isntance:",instance_id)
            instance.wait_until_running()
            print(f"Public Ip new Instance:",instance.public_ip_address)
            return instance.public_ip_address
    
if __name__ == '__main__':
   # ec2Manager = EC2Manager()
   # instance_id=ec2Manager.create_EC2_instance()
   # public_ip=ec2Manager.get_public_ip(instance_id)
   # print(public_ip)
   # print("Waiting for weblog available")
    public_ip="3.236.194.91"
    wait_for_port(7777,"3.236.194.91",220.0)
    print("Weblog app is ready!!!!!!")
    request_uuid=make_get_request("http://" + public_ip + ":7777/")
    print(f"http request done with uuid:",request_uuid)
    wait_backend_trace_id(request_uuid,30.0)
    
   
