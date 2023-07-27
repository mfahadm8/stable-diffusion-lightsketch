from typing import Dict
from constructs import Construct
from aws_cdk import (
    pipelines as pipelines,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_codedeploy as codedeploy,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
)
from .ecs_update_lambda import DeployLambda


class Pipeline(Construct):
    _config: Dict

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: Dict,
        ecs_cluster: ecs.Cluster,
        clientwebapp_service: ecs.FargateService,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._config = config

        webapp_repository = ecr.Repository.from_repository_arn(
            self,
            "ClientWebAppECRRepo",
            repository_arn=self._config["pipeline"]["webapp"]["repo_arn"],
        )

        # Create CodePipeline
        pipeline = codepipeline.Pipeline(
            self,
            "EcsPipeline-" + config["stage"],
            pipeline_name="EcsPipeline" + config["stage"],
        )

        # Create source actions for frontend and backend
        webapp_source_output = codepipeline.Artifact()
        webapp_source_action = codepipeline_actions.EcrSourceAction(
            action_name="webapp-source-action-" + config["stage"],
            repository=webapp_repository,
            image_tag=config["pipeline"]["webapp"]["image_tag"],
            output=webapp_source_output,
        )

        # Add source actions to the pipeline
        pipeline.add_stage(
            stage_name="Source",
            actions=[webapp_source_action],
        )

        # # Create SNS topic for manual approval
        if config["pipeline"]["manual_approval"]["required"]==True:
            approval_topic = sns.Topic(self, "ManualApprovalTopic")

            # Add email subscription to the SNS topic
            for email in self._config["pipeline"]["manual_approval"]["approver_emails"]:
                approval_topic.add_subscription(subscriptions.EmailSubscription(email_address=email))

            # Add manual approval action for prod pipeline
            manual_approval_action = codepipeline_actions.ManualApprovalAction(
                action_name="manual-approval-action-"+config["stage"],
                notification_topic=approval_topic,
            )

            # Add manual approval action to the pipeline
            prod_stage = pipeline.add_stage(stage_name="ManualApproval")
            prod_stage.add_action(manual_approval_action)


        deployment_lambda = DeployLambda(self, "DeploylambdaWebApp", self._config)

        webapp_lambda_deploy_action = codepipeline_actions.LambdaInvokeAction(
            action_name="webapp-lambda-deploy-action-" + config["stage"],
            inputs =[webapp_source_output],
            lambda_=deployment_lambda.deploy_lambda,
            user_parameters={
                "SERVICE_NAME": clientwebapp_service.service_name,
                "CLUSTER_NAME": ecs_cluster.cluster_name,
            },
            run_order=1,
        )

        # Add CodeDeploy actions to the pipeline
        pipeline.add_stage(
            stage_name="Deploy",
            actions=[webapp_lambda_deploy_action],
        )
