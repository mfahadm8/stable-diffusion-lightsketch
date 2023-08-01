import base64
import json

cloudwatch_agent_config = """
{
    "metrics": {
        "metrics_collected": {
            "nvidia_gpu": {
                "measurement": [
                    {"name": "memory_total", "rename": "nvidia_smi_memory_total", "unit": "Megabytes"},
                    {"name": "memory_used", "rename": "nvidia_smi_memory_used", "unit": "Megabytes"},
                    {"name": "memory_free", "rename": "nvidia_smi_memory_free", "unit": "Megabytes"}
                ],
                "metrics_collection_interval": 60
            }
        },
        "append_dimensions": {
            "ImageId": "${{aws:ImageId}}",
            "InstanceId": "${{aws:InstanceId}}",
            "InstanceType": "${{aws:InstanceType}}",
            "AutoScalingGroupName": "${{aws:AutoScalingGroupName}}"
        }
    }
}
"""
# Encode the configuration script in base64 and escape all quotes and newlines
encoded_cloudwatch_agent_config = base64.b64encode(json.dumps(cloudwatch_agent_config).encode('utf-8')).decode('utf-8').replace('\n', '')
print(encoded_cloudwatch_agent_config)
