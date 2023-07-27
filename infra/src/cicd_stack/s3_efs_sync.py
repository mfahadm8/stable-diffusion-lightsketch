from aws_cdk import (
    NestedStack,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_s3 as s3,
    aws_events_targets as events_targets,
    aws_lambda as lambda_,
    Duration,
    Size
)
from typing import Dict
from constructs import Construct


class S3EfsSyncLambda(Construct):
    _config: Dict
    _vpc = ec2.IVpc

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: Dict,
        vpc: ec2.Vpc,
        s3_bucket: s3.Bucket
    ) -> None:
        super().__init__(scope, id)
        self._config = config
        self._vpc = vpc,
        self._s3_bucket=s3_bucket,
        # Create cluster control plane
        self.__create_efs_s3_sync_lambda(vpc)



    def __create_efs_s3_sync_lambda(self):
        efs_mount_path = "/mnt/efs-volume-ml-model"

        lambda_func = lambda_.Function(
            self,
            "LambdaCopyFiles",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_asset("assets/lambda/testLambda"),
            environment={
                "BUCKET_NAME": self._s3_bucket.bucket.bucket_name,
                "EFS_MOUNT": efs_mount_path,
                "TEMP_DIR": "/tmp/download",
            },
            vpc=self._vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            filesystem=lambda_.FileSystem.from_efs_access_point(
                ap=self.efs_access_point, mount_path=efs_mount_path
            ),
            timeout=Duration.minutes(15),
            memory_size=1769,
            ephemeral_storage_size=Size.gibibytes(10),
        )
        self._s3_bucket.bucket.grant_read(lambda_func)