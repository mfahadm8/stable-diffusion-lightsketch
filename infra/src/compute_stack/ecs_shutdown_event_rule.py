from aws_cdk import (
    aws_events as events,
    aws_events_targets as targets,
    aws_lambda as _lambda,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_ecs as ecs,
    Duration
)
from constructs import Construct


class ALBRequestCountEventRule(Construct):
    def __init__(self, scope: Construct, id: str, cluster: ecs.ICluster, service: ecs.BaseService, alb: elbv2.ApplicationLoadBalancer, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create IAM role for the Lambda function
        lambda_role = iam.Role(
            self,
            "ALBRequestCountLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        # Allow the Lambda function to update the ECS service desired count
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ecs:UpdateService"],
                resources=[service.service_arn],
            )
        )

        # Create the Lambda function
        update_lambda_fn = _lambda.Function(
            self,
            "ALBRequestCountLambdaFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            handler="index.handler",
            code=_lambda.Code.from_inline(
                """
                import boto3

                ecs_client = boto3.client('ecs')

                def handler(event, context):
                    alb_arn = event['alb_arn']
                    service_arn = event['service_arn']

                    cloudwatch = boto3.client('cloudwatch')
                    response = cloudwatch.get_metric_data(
                        MetricDataQueries=[
                            {
                                'Id': 'requestCount',
                                'MetricStat': {
                                    'Metric': {
                                        'Namespace': 'AWS/ApplicationELB',
                                        'MetricName': 'RequestCount',
                                        'Dimensions': [
                                            {
                                                'Name': 'LoadBalancer',
                                                'Value': alb_arn
                                            }
                                        ]
                                    },
                                    'Period': 3600,
                                    'Stat': 'Sum',
                                    'Unit': 'Count',
                                },
                                'ReturnData': True
                            },
                        ],
                        StartTime=event['start_time'],
                        EndTime=event['end_time'],
                    )

                    # Check if there were no requestCount during the hour
                    if not response['MetricDataResults'][0]['Values']:
                        # Set desired count of the ECS service to 0
                        response = ecs_client.update_service(
                            cluster=event['cluster'],
                            service=event['service'],
                            desiredCount=0,
                        )
                        return {
                            'statusCode': 200,
                            'body': response
                        }

                    return {
                        'statusCode': 200,
                        'body': 'RequestCount found, no action required.'
                    }
                """
            ),
            role=lambda_role,
        )

        # Create the CloudWatch Events rule
        rule = events.Rule(
            self,
            "ALBRequestCountEventRule",
            schedule=events.Schedule.rate(Duration.hours(1)),
        )

        # Add the target to the rule
        rule.add_target(targets.LambdaFunction(update_lambda_fn))

        # Pass the necessary parameters to the Lambda function through input transformer
        rule.add_event_pattern(
            detail_type=['AWS API Call via CloudTrail'],
            detail={
                "eventSource": ["elasticloadbalancing.amazonaws.com"],
                "eventName": ["ModifyRule", "SetRulePriorities"],
                "requestParameters": {
                    "metricName": ["RequestCount"],
                    "dimensions": [
                        {
                            "name": "LoadBalancer",
                            "value": [alb.load_balancer_arn],
                        }
                    ],
                },
            }
        )

        # Grant necessary permissions to the Lambda function
        update_lambda_fn.grant_invoke_permissions(rule)
