from typing import Dict

from aws_cdk import (
    aws_ec2 as ec2,
    Stack
)
from utils.stack_util import add_tags_to_stack
from utils.ssm_util import SsmParameterFetcher
from constructs import Construct
from .s3 import S3 
from .efs import Efs
from .ecs import Ecs
from .s3_efs_sync import S3EfsSyncConstruct
class ComputeStack(Stack):

    def __init__(self, scope:Construct, id: str,
                 config: Dict,
                 vpc:ec2.IVpc,
                 ** kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Apply common tags to stack resources.
        add_tags_to_stack(self, config)
        # create the ecs cluster
        self._s3=S3(self,"ModelsBucket",config)
        self._efs=Efs(self,"ModelsEfs",config=config,vpc=vpc)
        self._ecs=Ecs(self, 'Ecs', config, vpc,self._efs.file_system)
        S3EfsSyncConstruct(self,"S3EfsSync",config=config,vpc=vpc,s3_bucket=self._s3.bucket,efs_access_point=self._efs.efs_access_point)
        
