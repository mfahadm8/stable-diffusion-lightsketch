from typing import Dict

from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_elasticloadbalancingv2 as elb2,
    aws_elasticloadbalancingv2_targets as targets,
    aws_ecs_patterns as ecs_patterns,
    aws_servicediscovery as servicediscovery,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ssm as ssm,
    aws_efs,
    aws_logs,
    aws_cloudwatch as cloudwatch,
    Duration,
    aws_autoscaling as autoscaling,
    aws_iam as iam,
    RemovalPolicy,
    Expiration
)
from constructs import Construct
from utils.ssm_util import SsmParameterFetcher
import base64
import json


class Ecs(Construct):
    _config: Dict
    _cluster: ecs.ICluster
    _lightsketch_app_service: ecs.FargateService
    _vpc = ec2.IVpc

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: Dict,
        vpc: ec2.Vpc,
        efs: aws_efs.FileSystem
    ) -> None:
        super().__init__(scope, id)
        self._config = config
        self._region=self._config["aws_region"]
        # Create cluster control plane
        self._vpc = vpc
        self._efs=efs
        self.__create_ecs_cluster()
        self.__create_lightsketch_app_container_def()
        self.__create_lightsketch_training_container_def()
        self.__create_lightsketch_app_service()
        self.__create_lightsketch_training_service()
        self.__setup_application_load_balancer()
        self.__setup_application_app_service_load_balancer_rule()
        self.__setup_application_training_service_load_balancer_rule()
        


    def __create_ecs_cluster(self):

        self.cluster_name="lightsketch_cluster_" + self._config["stage"]
        self._cluster = ecs.Cluster(
            self,
            "lightsketch",
            cluster_name=self.cluster_name,
            vpc=self._vpc
        )
        # Create private DNS namespace
        self.namespace = servicediscovery.PrivateDnsNamespace(
            self, "Namespace", name="lightsketch.local", vpc=self._vpc
        )

    def __create_lightsketch_training_container_def(self):

        # Import ECR repository for ui

        lightsketch_training_repository = ecr.Repository.from_repository_arn(
            self,
            "lightsketchTrainingECRRepo",
            repository_arn=self._config["compute"]["ecs"]["training"]["repo_arn"],
        )

        task_iam_role = self.__create_training_taskdef_role()

        # Create EC2 task definition for ui
        self.training_taskdef = ecs.Ec2TaskDefinition(
            self,
            "lightsketch-training-taskdef",
            task_role=task_iam_role,
            network_mode=ecs.NetworkMode.BRIDGE
        )

        training_container = self.training_taskdef.add_container(
            "container",
            image=ecs.ContainerImage.from_ecr_repository(
                lightsketch_training_repository,
                tag=self._config["compute"]["ecs"]["training"]["image_tag"],
            ),
            memory_limit_mib=self._config["compute"]["ecs"]["training"]["base_memory"],
            logging=ecs.LogDriver.aws_logs(
                stream_prefix="lightsketchtraining",
                log_group=aws_logs.LogGroup(
                    self,
                    "lightsketchTrainingServerLogGroup",
                    log_group_name="/ecs/lightsketchtraining-server",
                    retention=aws_logs.RetentionDays.ONE_WEEK,
                    removal_policy=RemovalPolicy.DESTROY,
                ),
            ),
            environment={
                "AWS_REGION": self._config["aws_region"],
            },
            gpu_count=self._config["compute"]["ecs"]["training"]["cuda"],

        )

        training_container.add_port_mappings(ecs.PortMapping(host_port=0,container_port=self._config["compute"]["ecs"]["training"]["port"]))

    def __create_lightsketch_app_container_def(self):

        # Import ECR repository for ui

        lightsketch_repository = ecr.Repository.from_repository_arn(
            self,
            "lightsketchappECRRepo",
            repository_arn=self._config["compute"]["ecs"]["app"]["repo_arn"],
        )

        task_iam_role = self.__create_app_taskdef_role()

        # Create EC2 task definition for ui
        self.app_taskdef = ecs.Ec2TaskDefinition(
            self,
            "lightsketch-taskdef",
            task_role=task_iam_role,
            network_mode=ecs.NetworkMode.BRIDGE
        )
        efs_volume_name = "efs-volume"
        efs_mount_path = "/mnt/app"
        self.app_taskdef.add_volume(
            name=efs_volume_name,
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=self._efs.file_system_id,
            ),
        )
        app_container = self.app_taskdef.add_container(
            "container",
            image=ecs.ContainerImage.from_ecr_repository(
                lightsketch_repository,
                tag=self._config["compute"]["ecs"]["app"]["image_tag"],
            ),
            memory_limit_mib=self._config["compute"]["ecs"]["app"]["base_memory"],
            logging=ecs.LogDriver.aws_logs(
                stream_prefix="lightsketchapp",
                log_group=aws_logs.LogGroup(
                    self,
                    "lightsketchappServerLogGroup",
                    log_group_name="/ecs/lightsketchapp-server",
                    retention=aws_logs.RetentionDays.ONE_WEEK,
                    removal_policy=RemovalPolicy.DESTROY,
                ),
            ),
            gpu_count=self._config["compute"]["ecs"]["app"]["cuda"],
            command=["bash","webui.sh","--nowebui",
                     "--no-gradio-queue",
                     "--ckpt-dir",efs_mount_path+"/models/StableDiffusion",
                     ]
        )

        app_container.add_port_mappings(ecs.PortMapping(host_port=0,container_port=self._config["compute"]["ecs"]["app"]["port"]))
        app_container.add_mount_points(
            ecs.MountPoint(
                source_volume=efs_volume_name,
                container_path=efs_mount_path,
                read_only=False,
            )
        )

    def __get_ec2_autoscaling_group(self,namespace):
        cloudwatch_agent_config = """
        {
            "metrics": {
                "namespace": "'{}'",
                "metrics_collected": {
                    "nvidia_gpu": {
                        "measurement": [
                            {"name": "memory_used", "rename": "nvidia_smi_memory_used", "unit": "Megabytes"}
                        ],
                        "metrics_collection_interval": 60
                    }
                },
                "aggregation_dimensions" : [[]]
            }
        }
        """.format(namespace)
        # Encode the configuration script in base64 and escape all quotes and newlines
        encoded_cloudwatch_agent_config = base64.b64encode(json.dumps(cloudwatch_agent_config).encode('utf-8')).decode('utf-8').replace('\n', '')

        user_data = ec2.UserData.for_linux(shebang="#!/usr/bin/bash")
        user_data_script = """#!/usr/bin/bash
        echo ECS_CLUSTER={} >> /etc/ecs/ecs.config
        sudo iptables --insert FORWARD 1 --in-interface docker+ --destination 169.254.169.254/32 --jump DROP
        sudo service iptables save
        echo ECS_AWSVPC_BLOCK_IMDS=true >> /etc/ecs/ecs.config
        echo ECS_ENABLE_GPU_SUPPORT=true >> /etc/ecs/ecs.config
        cat /etc/ecs/ecs.config
        sudo amazon-linux-extras install -y amazon-ssm-agent
        sudo systemctl start amazon-ssm-agent
        sudo systemctl enable amazon-ssm-agent
        sudo yum install -y amazon-cloudwatch-agent
        echo '{}' > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
        /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
        /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a start
        """.format(self.cluster_name ,cloudwatch_agent_config)

        user_data.add_commands(user_data_script)

        ec2_security_group = ec2.SecurityGroup(
            self,
            "Ec2BalancerSecurityGroup-"+namespace,
            vpc=self._cluster.vpc,
            allow_all_outbound=True,
        )
        ec2_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.all_tcp(),
        )

        asg = autoscaling.AutoScalingGroup(
            self,
            "ECSEC2Capacity-"+namespace,
            vpc=self._vpc,
            min_capacity=self._config["compute"]["ecs"]["app"]["minimum_containers"],
            desired_capacity=self._config["compute"]["ecs"]["app"]["minimum_containers"],
            max_capacity=self._config["compute"]["ecs"]["app"]["maximum_containers"],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC, one_per_az=True),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.G4DN, ec2.InstanceSize.XLARGE),
            machine_image=ec2.MachineImage.generic_linux(ami_map={
                self._region : self._config["compute"]["ecs"]["app"]["amis"][self._region]
                }),
            security_group=ec2_security_group,
            associate_public_ip_address=True,
            role=self.__create_ec2_role(),
            key_name=self._config["compute"]["ecs"]["app"]["ec2_keypair"],
            user_data=user_data,
            new_instances_protected_from_scale_in =False,
            block_devices=[
                # Add the desired root volume size to the block device mappings
                autoscaling.BlockDevice(
                    device_name="/dev/xvda",
                    volume=autoscaling.BlockDeviceVolume.ebs(
                        volume_size=100,
                        volume_type=autoscaling.EbsDeviceVolumeType.GP2,
                    ),
                )
            ]

        )
        
        return asg

    def __create_lightsketch_training_service(self):
        namespace="ls_training"
        asg=self.__get_ec2_autoscaling_group(namespace=namespace)
        # Create EC2 service for ui
        capacity_provider = ecs.AsgCapacityProvider(self, "AsgCapacityProvider-training",
            auto_scaling_group=asg,
            enable_managed_termination_protection = False,
            enable_managed_scaling = True

        )
        self._cluster.add_asg_capacity_provider(capacity_provider)

        self._lightsketch_training_service = ecs.Ec2Service(
            self,
            "lightsketchtraining-service",
            cluster=self._cluster,
            task_definition=self.training_taskdef,
            desired_count=1,  
            placement_constraints=[
                ecs.PlacementConstraint.distinct_instances()
            ],
            capacity_provider_strategies = [ecs.CapacityProviderStrategy(capacity_provider=capacity_provider.capacity_provider_name,base=1,weight=1)],
            health_check_grace_period=Duration.minutes(5)
        )


        self.__configure_service_autoscaling_rule(namespace,self._lightsketch_training_service)

    def __create_lightsketch_app_service(self):

        namespace="ls_app"
        asg=self.__get_ec2_autoscaling_group(namespace=namespace)
        capacity_provider = ecs.AsgCapacityProvider(self, "AsgCapacityProvider-app",
            auto_scaling_group=asg,
            enable_managed_termination_protection = False,
            enable_managed_scaling = True

        )
        self._cluster.add_asg_capacity_provider(capacity_provider)

        self._lightsketch_app_service = ecs.Ec2Service(
            self,
            "lightsketchapp-service",
            cluster=self._cluster,
            task_definition=self.app_taskdef,
            desired_count=1,  
            placement_constraints=[
                ecs.PlacementConstraint.distinct_instances()
            ],
            capacity_provider_strategies = [ecs.CapacityProviderStrategy(capacity_provider=capacity_provider.capacity_provider_name,base=1,weight=1)],
            health_check_grace_period=Duration.minutes(5)
        )

        self.__configure_service_autoscaling_rule(namespace,self._lightsketch_app_service)

    def __create_ec2_role(self) -> iam.Role:
        # Create IAM role for EC2 instances
        role = iam.Role(
            self,
            "ec2-role-"+self._config["stage"],
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
        )

        # Add necessary permissions to the EC2 role
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonECS_FullAccess")
            )
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonEC2ContainerServiceforEC2Role")
            )
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonEC2RoleforSSM")
            )
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchAgentServerPolicy")
        )

        return role
    
    def __create_app_taskdef_role(self) -> iam.Role:
        # Create IAM role for task definition
        task_role = iam.Role(
            self,
            "app-task-role-" + self._config["stage"],
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # Attach S3 full access policy to the task role
        task_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess")
        )
        region=self._config["aws_region"]
        account=self._config["aws_account"]
        task_role.add_to_policy(
             iam.PolicyStatement(
                actions=[
                    "elasticfilesystem:ClientRootAccess",
                    "elasticfilesystem:ClientWrite",
                    "elasticfilesystem:ClientMount",
                    "elasticfilesystem:DescribeMountTargets",
                ],
                resources=[
                    f"arn:aws:elasticfilesystem:{region}:{account}:file-system/{self._efs.file_system_id}"
                ],
            )
        )
        task_role.add_to_policy( 
            iam.PolicyStatement(
                actions=["ec2:DescribeAvailabilityZones"],
                resources=["*"],
            ))

        return task_role


    def __create_training_taskdef_role(self) -> iam.Role:
        # Create IAM role for task definition
        task_role = iam.Role(
            self,
            "training-task-role-" + self._config["stage"],
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # Attach S3 full access policy to the task role
        task_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess")
        )

        task_role.add_to_policy(
             iam.PolicyStatement(
                actions=[
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "kms:Decrypt",
                    "kms:GenerateDataKey"
                ],
                resources=[
                   "*"
                ],
            )
        )
        task_role.add_to_policy( 
            iam.PolicyStatement(
                actions=["ec2:DescribeAvailabilityZones"],
                resources=["*"],
            ))

        return task_role
    

    def __setup_application_load_balancer(self):
        # Create security group for the load balancer
        lb_security_group = ec2.SecurityGroup(
            self,
            "LoadBalancerSecurityGroup",
            vpc=self._cluster.vpc,
            allow_all_outbound=True,
        )
        lb_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
        )

        # Create load balancer
        self.lb = elbv2.ApplicationLoadBalancer(
            self,
            "LoadBalancer",
            vpc=self._cluster.vpc,
            internet_facing=True,
            security_group=lb_security_group,
        )

    def __setup_application_app_service_load_balancer_rule(self):
        # Create target group
        app_target_group = elbv2.ApplicationTargetGroup(
            self,
            "TargetGroup-App",
            vpc=self._cluster.vpc,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[self._lightsketch_app_service],
            health_check=elbv2.HealthCheck(
                path="/sdapi/v1/sd-models",
                protocol=elbv2.Protocol.HTTP,
                interval=Duration.seconds(60),
                timeout=Duration.seconds(30),
                healthy_threshold_count=2,
                unhealthy_threshold_count=5,
            ),
        )

        # Create HTTP listener for redirection
        self.lb_http_listener = self.lb.add_listener(
            "HttpListener", port=80, protocol=elbv2.ApplicationProtocol.HTTP,
            default_target_groups=[app_target_group],

        )


    def __setup_application_training_service_load_balancer_rule(self):
        # Create target group
        training_target_group = elbv2.ApplicationTargetGroup(
            self,
            "TargetGroup-Training",
            vpc=self._cluster.vpc,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[self._lightsketch_training_service],
            health_check=elbv2.HealthCheck(
                path="/training/",
                protocol=elbv2.Protocol.HTTP,
                interval=Duration.seconds(60),
                timeout=Duration.seconds(30),
                healthy_threshold_count=2,
                unhealthy_threshold_count=5,
            ),
        )
        
        # Create the listener rule
        rule = elbv2.CfnListenerRule(
            self,
            "ListenerRule",
            listener_arn=self.lb_http_listener.listener_arn,
            priority=1,
            actions=[
                elbv2.CfnListenerRule.ActionProperty(
                    type="forward",
                    target_group_arn =training_target_group.target_group_arn,
                )
            ],
            conditions=[
                elbv2.CfnListenerRule.RuleConditionProperty(
                    field="path-pattern",
                    values=["/training/*"],
                )
            ],
        )

        rule.add_dependency(training_target_group.node.default_child)



    def __configure_service_autoscaling_rule(self,namespace,ecs_service):

        # Add GPU VRAM scaling based on the CloudWatch metrics
        gpu_vram_metric = cloudwatch.Metric(
            namespace=namespace,
            metric_name="nvidia_smi_memory_used",
            period=Duration.minutes(1),
            statistic="Average"
        )

        gpu_scaling = autoscaling.ScalableTarget(
            self,
            "gpu-vram-scaling-"+namespace,
            service_namespace=autoscaling.ServiceNamespace.ECS,
            resource_id=f"service/{self._cluster.cluster_name}/{ecs_service.service_name}",
            scalable_dimension="ecs:service:DesiredCount",
            min_capacity=self._config["compute"]["ecs"]["app"]["minimum_containers"],
            max_capacity=self._config["compute"]["ecs"]["app"]["maximum_containers"],
        )

        gpu_scaling.scale_on_metric(
            "ScaleToGPURAMUsage-"+namespace,
            metric=gpu_vram_metric,
            scaling_steps=[
                autoscaling.ScalingInterval(change=+1, lower=8000),
                autoscaling.ScalingInterval(change=-1, lower=8000),
            ],
            evaluation_periods=2,
            cooldown=Duration.minutes(5),
            adjustment_type=autoscaling.AdjustmentType.CHANGE_IN_CAPACITY
        )