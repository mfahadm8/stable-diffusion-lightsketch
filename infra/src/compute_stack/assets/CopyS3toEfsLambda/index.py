import logging
import os
import boto3
import urllib.parse
logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

EFS_MOUNT = os.getenv("EFS_MOUNT")
TEMP_DIR = os.getenv("TEMP_DIR","/tmp")


def handler(events, context):
    logger.info(events)
    for record in events["Records"]:
        bucket_name=urllib.parse.unquote(record["s3"]["bucket"]["name"])
        s3_file_path=urllib.parse.unquote(record["s3"]["object"]["key"])
        local_temp_file = f"{TEMP_DIR}/{s3_file_path}"
        efs_file_path = f"{EFS_MOUNT}/{s3_file_path}"
        tmp_folder_path = os.path.dirname(local_temp_file)
        os.makedirs(tmp_folder_path, exist_ok=True)
        efs_folder_path = os.path.dirname(efs_file_path)
        os.makedirs(efs_folder_path, exist_ok=True)
        logger.info(s3_file_path)
        with open(local_temp_file, "wb") as f:
            s3.download_fileobj(bucket_name, s3_file_path, f)

        os.system(f"cp {local_temp_file} {efs_folder_path}")

        logger.info(os.system(f"ls -la {EFS_MOUNT}"))

    return {"statusCode": 200}