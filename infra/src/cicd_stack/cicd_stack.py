from aws_cdk import (
    aws_ecs as ecs,
    Stack,
)
from constructs import Construct
from utils.stack_util import add_tags_to_stack
from typing import Dict
from .ecs_pipeline import Pipeline


class CICDStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        config: Dict,
        ecs_cluster: ecs.ICluster,
        app_service: ecs.FargateService,
        **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)
        self._config = config

        # Apply common tags to stack resources.
        add_tags_to_stack(self, self._config)
        Pipeline(
            self,
            "EcsPipeline-" + self._config["stage"],
            self._config,
            ecs_cluster=ecs_cluster,
            clientwebapp_service=app_service
        )
