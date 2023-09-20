import boto3
import os
import sys

# Read AWS credentials and region from environment variables
AWS_ACCESS_KEY_ID = os.environ.get('AWSAccessKeyID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWSSecretAccessKey')
AWS_REGION = os.environ.get('AWSRegion')
S3_BUCKET_NAME = 'inbound-pdfs'

def upload_file_to_s3(file_path, s3_bucket_name):
    try:
        # Initialize the S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )

        # Extract the file name from the path
        file_name = os.path.basename(file_path)

        # Upload the file to the specified S3 bucket
        s3_client.upload_file(file_path, s3_bucket_name, file_name)

        print(f"File '{file_name}' uploaded to S3 bucket '{s3_bucket_name}' successfully.")
    except Exception as e:
        print(f"Error uploading file: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python epsi-text-extraction.py <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]
    upload_file_to_s3(file_path, S3_BUCKET_NAME)