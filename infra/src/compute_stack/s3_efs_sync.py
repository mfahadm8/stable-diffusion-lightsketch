from aws_cdk import (
    NestedStack,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_s3 as s3,
    aws_lambda_event_sources,
    aws_events_targets as events_targets,
    aws_lambda as lambda_,
    aws_efs as efs,
    Duration,
    Size
)
from typing import Dict
from constructs import Construct


class S3EfsSyncConstruct(Construct):
    _config: Dict
    _vpc = ec2.IVpc

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: Dict,
        vpc: ec2.Vpc,
        s3_bucket: s3.Bucket,
        efs_access_point: efs.AccessPoint
    ) -> None:
        super().__init__(scope, id)
        self._config = config
        self._vpc = vpc
        self._s3_bucket=s3_bucket
        self.efs_access_point=efs_access_point
        # Create cluster control plane
        self.__create_efs_s3_sync_lambda()



    def __create_efs_s3_sync_lambda(self):
        efs_mount_path = "/mnt/app"

        lambda_func = lambda_.Function(
            self,
            "LambdaCopyFiles",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_asset("src/compute_stack/assets/CopyS3toEfsLambda"),
            environment={
                "BUCKET_NAME": self._s3_bucket.bucket_name,
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
            ephemeral_storage_size=Size.gibibytes(10),
            memory_size=1769
        )
        self._s3_bucket.grant_read(lambda_func)


        lambda_func.add_event_source(aws_lambda_event_sources.S3EventSource(self._s3_bucket,
            events=[s3.EventType.OBJECT_CREATED],
            filters=[s3.NotificationKeyFilter(prefix="models/")]
        ))