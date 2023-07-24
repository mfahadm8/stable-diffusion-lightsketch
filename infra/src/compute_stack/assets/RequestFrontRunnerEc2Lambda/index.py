import boto3
import time
import json
import urllib
import requests

def start_ec2_instance(instance_id):
    ec2_client = boto3.client('ec2')
    ec2_client.start_instances(InstanceIds=[instance_id])
    ec2_client.get_waiter('instance_running').wait(InstanceIds=[instance_id])

def stop_ec2_instance(instance_id):
    ec2_client = boto3.client('ec2')
    ec2_client.stop_instances(InstanceIds=[instance_id])

def get_instance_ip(instance_id):
    ec2_client = boto3.client('ec2')
    response = ec2_client.describe_instances(InstanceIds=[instance_id])
    return response['Reservations'][0]['Instances'][0]['PublicIpAddress'] if 'PublicIpAddress' in response['Reservations'][0]['Instances'][0] else False

def lambda_handler(event, context):
    # Replace 'your_ec2_instance_id' with the actual ID of your EC2 instance
    ec2_instance_id = 'i-080e5b02e10d92380'

    # Start the EC2 instance if it's not already running
    ec2_instance_ip = get_instance_ip(ec2_instance_id)
    if not ec2_instance_ip:
        start_ec2_instance(ec2_instance_id)
        ec2_instance_ip = get_instance_ip(ec2_instance_id)

    # Wait for the EC2 instance to be healthy (you can customize the health check endpoint)
    ec2_health_check_endpoint = f"http://{ec2_instance_ip}:8000/healthcheck"
    while True:
        try:
            response = requests.get(ec2_health_check_endpoint)
            response.raise_for_status()
            break
        except requests.exceptions.RequestException:
            time.sleep(5)

    # Send the POST request to the EC2 instance
    response = requests.post(f"http://{ec2_instance_ip}:8000", data=event["body"])

    # Stop the EC2 instance after it has completed its work
    stop_ec2_instance(ec2_instance_id)

    return {
        'statusCode': 200,
        'body': response.text
    }
