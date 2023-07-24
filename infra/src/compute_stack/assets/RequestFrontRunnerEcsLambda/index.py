import boto3
import time
import json
import urllib
import requests

def lambda_handler(event, context):
    # Replace 'your_ecs_cluster_name' with the actual name of your ECS cluster
    ecs_cluster_name = 'lightsketch_cluster_dev'
    ecs_service_name = 'ComputeStack-dev-EcslightsketchappserviceService0FE39A10-BzolpbHZKLeO'

    # Replace 'your_load_balancer_name' with the actual name of your load balancer
    load_balancer_name = 'Compu-EcsLo-1Y2KOURPUS6VF'

    # Update the desired capacity of the ECS service to 1
    ecs_client = boto3.client('ecs')
    response = ecs_client.describe_services(cluster=ecs_cluster_name, services=[ecs_service_name])
    if 'services' in response and len(response['services']) > 0:
        desired_count = response['services'][0].get('desiredCount', 0)
        if desired_count == 0:
            response = ecs_client.update_service(
                cluster=ecs_cluster_name,
                service=ecs_service_name,
                desiredCount=1
            )
            print("service started")
        else:
            print("service already running")

    
    # Wait for the load balancer to become healthy
    elbv2_client = boto3.client('elbv2')
    target_group_arn = None
    
    # Find the target group associated with the load balancer
    load_balancer_arn = None
    response = elbv2_client.describe_load_balancers(Names=[load_balancer_name])
    if 'LoadBalancers' in response:
        load_balancer_arn = response['LoadBalancers'][0]['LoadBalancerArn']
    
    # Find the target group attached to the ECS service
    if load_balancer_arn:
        response = elbv2_client.describe_target_groups(LoadBalancerArn=load_balancer_arn)
        if 'TargetGroups' in response:
            target_group_arn = response['TargetGroups'][0]['TargetGroupArn']
    
    # Wait for the target group to have healthy targets
    if target_group_arn:
        while True:
            response = elbv2_client.describe_target_health(TargetGroupArn=target_group_arn)
            if 'TargetHealthDescriptions' in response:
                healthy_targets = [target for target in response['TargetHealthDescriptions'] if target['TargetHealth']['State'] == 'healthy']
                if len(healthy_targets) > 0:
                    break
            time.sleep(5)
    
    # Get the load balancer DNS associated with the ECS service
    lb_dns = None
    if load_balancer_arn:
        response = elbv2_client.describe_load_balancers(Names=[load_balancer_name])
        if 'LoadBalancers' in response:
            lb_dns = response['LoadBalancers'][0]['DNSName']
    
    # Prepare the redirection URL
    if lb_dns:
        response=requests.post(f"http://{lb_dns}",data=event["body"])
    
        ecs_client.update_service(
                cluster=ecs_cluster_name,
                service=ecs_service_name,
                desiredCount=0
            )
        return {
            'statusCode': 200,
            'body': json.loads(response.text)
        }
    
    ecs_client.update_service(
        cluster=ecs_cluster_name,
        service=ecs_service_name,
        desiredCount=0
        )
    # If load balancer DNS not found, return a failure response
    return {
        'statusCode': 500,
        'body': 'Something went wrong'
    }
