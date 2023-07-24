LOCAL_VENV_NAME=.venv
PYTHON=python3
STACK?=NetworkStack

STAGE?= dev
ifeq ($(STAGE), prod)
	REGION=us-west-2
else
	REGION=us-east-1
endif

setup-codebuild:
	aws cloudformation deploy --template-file ./cloudformation/codebuild/docker_build.yml --stack-name CodebuildDockerPushStack --region $(REGION) --capabilities CAPABILITY_NAMED_IAM

synth:
	@cdk synth -c stage=$(STAGE) --output=cdk.out/$(STAGE) $(STACK)-$(STAGE)

deploy:
	@cdk deploy --app=cdk.out/$(STAGE) $(STACK)-$(STAGE)

diff:
	@cdk diff -c stage=$(STAGE) $(STACK)-$(STAGE)

destroy:
	@cdk destroy -c stage=$(STAGE) $(STACK)-$(STAGE)

bootstrapp-cdk-toolkit:
	@cdk bootstrap aws://$(shell cat config/$(STAGE).yaml | yq -r '.awsAccount')/$(shell cat config/$(STAGE).yaml | yq -r '.aws_region') -c stage=$(STAGE)