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
    aws_efs,
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
        efs: aws_efs.FileSystem
    ) -> None:
        super().__init__(scope, id)
        self._config = config
        # Create cluster control plane
        self._vpc = vpc
        self._efs=efs
        self.__create_ecs_cluster()
        self.__create_lightsketch_service()


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
        efs_volume_name = "efs-volume"
        efs_mount_path = "/efs/app/models"
        app_taskdef.add_volume(
            name=efs_volume_name,
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=self._efs.file_system_id,
            ),
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
            gpu_count=self._config["compute"]["ecs"]["app"]["cuda"],
            command=["python3","launch.py","--nowebui",
                     "--hypernetwork-dir",efs_mount_path+"/hypernetworks"
                     "--codeformer-models-path",efs_mount_path+"/Codeformer",
                     "--gfpgan-models-path",efs_mount_path+"/GFPGAN",
                     "--esrgan-models-path",efs_mount_path+"/ESRGAN",
                     "--bsrgan-models-path",efs_mount_path+"/BSRGAN",
                     "--realesrgan-models-path",efs_mount_path+"/RealESRGAN",
                     "--clip-models-path",efs_mount_path+"/CLIP"
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

        launch_template = ec2.LaunchTemplate(
            self,
            "LightsketchLaunchTemplate",
            launch_template_name="LightsketchLaunchTemplate",  # Give it a name
            version="1",  # Specify a version for the launch template
            block_devices=[
                # Add the desired root volume size to the block device mappings
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_size=100,
                        volume_type=ec2.EbsDeviceVolumeType.GP2,
                    ),
                )
            ],
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.G4DN, ec2.InstanceSize.XLARGE),
            machine_image=ec2.MachineImage.generic_linux(ami_map={"us-east-1": "ami-03a32d185474e28bc"})
            
        )

        self.asg = autoscaling.AutoScalingGroup(
            self,
            "ECSEC2SpotCapacity",
            vpc=self._vpc,
            min_capacity=self._config["compute"]["ecs"]["app"]["minimum_containers"],
            desired_capacity=self._config["compute"]["ecs"]["app"]["minimum_containers"],
            max_capacity=self._config["compute"]["ecs"]["app"]["maximum_containers"],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC, one_per_az=True),
            spot_price="0.50",
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
            ],
            launch_template=launch_template,
            mixed_instances_policy=autoscaling.MixedInstancesPolicy(
            launch_template_overrides=[autoscaling.LaunchTemplateOverrides(instance_type=ec2.InstanceType("g4dn.xlarge")), autoscaling.LaunchTemplateOverrides(instance_type=ec2.InstanceType("g5.xlarge")), autoscaling.LaunchTemplateOverrides(instance_type=ec2.InstanceType("g3.4xlarge"),launch_template=launch_template)]
        ),

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
            desired_count=1,       
            placement_strategies=[
                ecs.PlacementStrategy.spread_across_instances(),
                ecs.PlacementStrategy.packed_by_cpu(),
                ecs.PlacementStrategy.randomly()
            ],
            placement_constraints=[
                ecs.PlacementConstraint.distinct_instances()
            ],
            capacity_provider_strategies = [ecs.CapacityProviderStrategy(capacity_provider=capacity_provider.capacity_provider_name,base=1,weight=1)]
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
        http_listener = self.lb.add_listener(
            "HttpListener", port=80, protocol=elbv2.ApplicationProtocol.HTTP,
            default_target_groups=[target_group],

        )