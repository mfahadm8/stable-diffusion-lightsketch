import boto3
import json
import traceback
import os


REGION=os.environ.get("CLUSTER_REGION")
ecs = boto3.client("ecs",region_name=REGION)
codepipeline = boto3.client('codepipeline')

def handler(event, context):
    print(event)
    try:
        jobId = event['CodePipeline.job']['id']
        params = json.loads(event['CodePipeline.job']['data']['actionConfiguration']['configuration']['UserParameters'])

        CLUSTER_NAME = params.get("CLUSTER_NAME")
        SERVICE_NAME = params.get("SERVICE_NAME")
        response = ecs.update_service(
            cluster=CLUSTER_NAME, service=SERVICE_NAME, forceNewDeployment=True
        )
        print(response)
        response = codepipeline.put_job_success_result(jobId=jobId)
    except Exception as e:
        response = codepipeline.put_job_failure_result(
            jobId=jobId,
            failureDetails={
                'message': str(traceback.print_exc()),
                'type': 'JobFailed',
                'externalExecutionId': context.aws_request_id
            }
        )
