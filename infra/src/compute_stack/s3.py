from typing import Dict

from aws_cdk import (
    aws_s3 as s3,
    RemovalPolicy,
)
from constructs import Construct
from utils.ssm_util import SsmParameterFetcher


class S3(Construct):
    _config: Dict

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: Dict,
    ) -> None:
        super().__init__(scope, id)
        self._config = config
        self.bucket = s3.Bucket(
            self, "lightsketch-models-bucket"+self._config["stage"], removal_policy=RemovalPolicy.DESTROY
        )