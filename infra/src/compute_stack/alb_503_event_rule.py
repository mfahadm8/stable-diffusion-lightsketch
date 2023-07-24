from aws_cdk import (
    aws_events as events,
    aws_events_targets as targets,
    aws_elasticloadbalancingv2 as elbv2,
    aws_lambda as _lambda,
    aws_ecs as ecs,
    aws_iam as iam,
)
from constructs import Construct


class ALBEventRule(Construct):
    def __init__(self, scope: Construct, id: str, cluster: ecs.ICluster, load_balancer: elbv2.ApplicationLoadBalancer, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create IAM role for the Lambda function
        lambda_role = iam.Role(
            self,
            "ALBUpdateLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        # Allow the Lambda function to update the ECS cluster desired capacity
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ecs:UpdateService"],
                resources=[cluster.cluster_arn],
            )
        )

        # Create the Lambda function
        update_lambda_fn = _lambda.Function(
            self,
            "ALBUpdateLambdaFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            handler="index.handler",
            code=_lambda.Code.from_inline(
                """
                import boto3

                ecs_client = boto3.client('ecs')

                def handler(event, context):
                    response = ecs_client.update_service(
                        cluster=event['cluster'],
                        service=event['service'],
                        desiredCount=1,
                    )
                    return {
                        'statusCode': 200,
                        'body': response
                    }
                """
            ),
            role=lambda_role,
        )

        # Create the CloudWatch Events rule
        rule = events.Rule(
            self,
            "ALBEventRule",
            event_pattern={
                "source": ["aws.applicationELB"],
                "detail": {
                    "eventName": ["ModifyRule", "SetRulePriorities"],
                    "requestParameters": {
                        "metricName": ["HTTPCode_ELB_503_Count"]
                    },
                },
            },
        )

        # Add the target to the rule
        rule.add_target(targets.LambdaFunction(update_lambda_fn))

        # Grant necessary permissions to the Lambda function
        update_lambda_fn.grant_invoke_permissions(rule)

        # Make sure the Lambda function runs before the ECS service autoscaling
        cluster.autoscaling_group.add_depends_on(update_lambda_fn)
