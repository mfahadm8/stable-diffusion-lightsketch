from typing import Dict

from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_elasticloadbalancingv2 as elb2,
    aws_ecs_patterns as ecs_patterns,
    aws_servicediscovery as servicediscovery,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ssm as ssm,
    aws_logs,
    aws_cloudwatch as cloudwatch,
    Duration,
    aws_autoscaling as autoscaling,
    aws_iam as iam,
    RemovalPolicy,
)
from constructs import Construct
from utils.ssm_util import SsmParameterFetcher


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
    ) -> None:
        super().__init__(scope, id)
        self._config = config
        # Create cluster control plane
        self.__create_ecs_cluster(vpc)
        self.__create_lightsketch_service()


    def __create_ecs_cluster(self, vpc: ec2.Vpc):
        # Create ECS cluster
        self._vpc = vpc
        self.cluster_name="lightsketch_cluster_" + self._config["stage"]
        self._cluster = ecs.Cluster(
            self,
            "lightsketch",
            cluster_name=self.cluster_name,
            vpc=vpc
        )
        # Create private DNS namespace
        self.namespace = servicediscovery.PrivateDnsNamespace(
            self, "Namespace", name="ecs.local", vpc=vpc
        )

    def __create_lightsketch_service(self):

        # Import ECR repository for ui

        lightsketch_repository = ecr.Repository.from_repository_arn(
            self,
            "lightsketchappECRRepo",
            repository_arn=self._config["compute"]["ecs"]["app"]["repo_arn"],
        )

        task_iam_role = self.__create_app_taskdef_role()

        # Create EC2 task definition for ui
        app_taskdef = ecs.Ec2TaskDefinition(
            self,
            "lightsketch-taskdef",
            task_role=task_iam_role,
            network_mode=ecs.NetworkMode.BRIDGE
        )

        app_container = app_taskdef.add_container(
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
            gpu_count=self._config["compute"]["ecs"]["app"]["cuda"]
        )

        app_container.add_port_mappings(ecs.PortMapping(host_port=0,container_port=8000))


        user_data=ec2.UserData.for_linux(shebang="#!/usr/bin/bash")
        user_data_script = f"""#!/usr/bin/bash
        echo ECS_CLUSTER={self.cluster_name} >> /etc/ecs/ecs.config
        sudo iptables --insert FORWARD 1 --in-interface docker+ --destination 169.254.169.254/32 --jump DROP
        sudo service iptables save
        echo ECS_ENABLE_SPOT_INSTANCE_DRAINING=true >> /etc/ecs/ecs.config
        echo ECS_AWSVPC_BLOCK_IMDS=true >> /etc/ecs/ecs.config
        echo ECS_ENABLE_GPU_SUPPORT=true >> /etc/ecs/ecs.config
        cat /etc/ecs/ecs.config
        sudo amazon-linux-extras install -y amazon-ssm-agent
        sudo systemctl start amazon-ssm-agent
        sudo systemctl enable amazon-ssm-agent
        """
        user_data.add_commands(user_data_script)

        ec2_security_group = ec2.SecurityGroup(
            self,
            "Ec2BalancerSecurityGroup",
            vpc=self._cluster.vpc,
            allow_all_outbound=True,
        )
        ec2_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.all_tcp(),
        )

        self.asg = autoscaling.AutoScalingGroup(
            self,
            "ECSEC2SpotCapacity",
            vpc=self._vpc,
            min_capacity=0,
            desired_capacity=0,
            max_capacity=self._config["compute"]["ecs"]["app"]["maximum_containers"],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC, one_per_az=True),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.G3, ec2.InstanceSize.XLARGE4),
            machine_image=ec2.MachineImage.generic_linux(ami_map={"us-east-1": "ami-03a32d185474e28bc"}),
            spot_price="0.50",
            security_group=ec2_security_group,
            associate_public_ip_address=True,
            role=self.__create_ec2_role(),
            key_name=self._config["compute"]["ecs"]["app"]["ec2_keypair"],
            user_data=user_data,
            new_instances_protected_from_scale_in =False

        )
        
        capacity_provider = ecs.AsgCapacityProvider(self, "AsgCapacityProvider",
            auto_scaling_group=self.asg,
            enable_managed_termination_protection = False,
            spot_instance_draining = True,
            enable_managed_scaling = True

        )
        self._cluster.add_asg_capacity_provider(capacity_provider)

        # Create EC2 service for ui
        self._lightsketch_app_service = ecs.Ec2Service(
            self,
            "lightsketchapp-service",
            cluster=self._cluster,
            task_definition=app_taskdef,
            desired_count=0,
            capacity_provider_strategies = [ecs.CapacityProviderStrategy(capacity_provider=capacity_provider.capacity_provider_name,weight=1)]
        )

        self.__setup_application_load_balancer()


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
        # Add additional policies if needed

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
        lb = elbv2.ApplicationLoadBalancer(
            self,
            "LoadBalancer",
            vpc=self._cluster.vpc,
            internet_facing=True,
            security_group=lb_security_group,
        )

        # Create target group
        target_group = elbv2.ApplicationTargetGroup(
            self,
            "TargetGroup",
            vpc=self._cluster.vpc,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[self._lightsketch_app_service],
            health_check=elbv2.HealthCheck(
                path="/healthcheck",
                protocol=elbv2.Protocol.HTTP,
                interval=Duration.seconds(30),
                timeout=Duration.seconds(20),
                healthy_threshold_count=5,
                unhealthy_threshold_count=5,
            ),
        )

        # Create HTTP listener for redirection
        http_listener = lb.add_listener(
            "HttpListener", port=80, protocol=elbv2.ApplicationProtocol.HTTP,
            default_target_groups=[target_group],

        )