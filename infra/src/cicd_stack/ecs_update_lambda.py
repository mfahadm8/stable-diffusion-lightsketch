from aws_cdk import (
    NestedStack,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_events_targets as events_targets,
    aws_lambda as lambda_,
)
from typing import Dict
from constructs import Construct


class DeployLambda(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        config: Dict,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.deploy_lambda = lambda_.Function(
            self,
            id + "-" + config["stage"],
            code=lambda_.Code.from_asset("src/deploy_stack/EcsServiceUpdateLambda/assets"),
            handler="index.handler",
            runtime=lambda_.Runtime.PYTHON_3_9,
            retry_attempts=1,
            memory_size=128,
            environment={
                "CLUSTER_REGION":config["compute"]["aws_region"]
            }
        )
        self.deploy_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ecs:UpdateService"],
                resources=["*"],
            )
        )
