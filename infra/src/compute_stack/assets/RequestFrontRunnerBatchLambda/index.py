import boto3
import time

batch_client = boto3.client('batch')
logs_client = boto3.client('logs')

def lambda_handler(event, context):
    # Step 1: Trigger AWS Batch job
    response = batch_client.submit_job(
        jobDefinition='your-job-definition-name',
        jobName='your-job-name',
        jobQueue='your-job-queue',
        # Add any other relevant parameters or input data for your Batch job
    )
    
    job_id = response['jobId']
    
    # Step 2: Wait for the AWS Batch job to complete
    while True:
        job_status = batch_client.describe_jobs(jobs=[job_id])['jobs'][0]['status']
        if job_status in ['SUCCEEDED', 'FAILED']:
            break
        time.sleep(5)  # Add a delay between checks to avoid excessive API calls
    
    # Step 3: Retrieve CloudWatch Logs for the job
    log_group_name = '/aws/batch/job'  # Modify this to match your CloudWatch Log Group for Batch jobs
    log_stream_name = f'{job_id}/{job_id}'
    logs_response = logs_client.get_log_events(
        logGroupName=log_group_name,
        logStreamName=log_stream_name,
        startFromHead=True
    )
    
    # Step 4: Extract and use the response from CloudWatch Logs
    logs = logs_response['events']
    # Process the logs to extract the relevant data or response
    
    return {
        'statusCode': 200,
        'body': 'Response from Batch Job: ' + logs
    }
