from typing import Dict

from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_efs as efs,
    aws_ssm as ssm,
    RemovalPolicy,
)
from constructs import Construct
from utils.ssm_util import SsmParameterFetcher


class Efs(Construct):
    _config: Dict
    _vpc = ec2.IVpc

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: Dict,
        vpc: ec2.Vpc,
    ) -> None:
        super().__init__(scope, id)
        self._config = config
        self._vpc = vpc
        # Create cluster control plane
        self.__create_efs(vpc)


    def __create_efs(self, vpc: ec2.Vpc):

        self.file_system = efs.FileSystem(
            self,
            "EfsFileSystemService-"+ self._config["stage"],
            vpc=self._vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            lifecycle_policy=efs.LifecyclePolicy.AFTER_1_DAY,
            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,
            out_of_infrequent_access_policy=efs.OutOfInfrequentAccessPolicy.AFTER_1_ACCESS,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.efs_access_point = self.file_system.add_access_point(
            "EfsAccessPoint",
            create_acl=efs.Acl(owner_uid="0", owner_gid="0", permissions="777"),
            posix_user=efs.PosixUser(uid="0", gid="0"),
        )

        self.file_system.connections.allow_default_port_from_any_ipv4()

    
