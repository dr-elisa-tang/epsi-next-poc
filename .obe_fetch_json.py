import boto3
import os
import sys

# Read AWS credentials and region from environment variables
AWS_ACCESS_KEY_ID = os.environ.get('AWSAccessKeyID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWSSecretAccessKey')
AWS_REGION = os.environ.get('AWSRegion')
OUTBOUND_S3 = 'outbound-jsons'

def get_json(file_name):
    try:
        # Initialize the S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )

        # Retrieve the object from S3
        response = s3_client.get_object(Bucket=OUTBOUND_S3, Key=file_name)

        # Read and display the contents of the object (file)
        file_contents = response['Body'].read().decode('utf-8')
        print(f"Contents of '{file_name}':\n{file_contents}")
    except Exception as e:
        print(f"Error retrieving and displaying file: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python epsi-text-extraction.py <file_path>")
        sys.exit(1)

    # Assuming the uploaded file is named the same as the local file
    file_name = sys.argv[1]
    get_json(file_name)