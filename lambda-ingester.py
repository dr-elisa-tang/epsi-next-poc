import os
import sys
import boto3

# Set the input and output bucket names
input_bucket_name = "epsi-next-poc-in"
output_bucket_name = "epsi-next-poc-out"

def main():
    # Initialize the Textract client
    textract_client = boto3.client('textract')

    # Process each PDF file in the input S3 bucket
    s3 = boto3.client('s3')
    response = s3.list_objects_v2(Bucket=input_bucket_name)

    for obj in response.get('Contents', []):
        file_name = obj['Key']

        if file_name.lower().endswith(".pdf"):
            print(f"Processing: s3://{input_bucket_name}/{file_name}")

            # Send the PDF file to Textract
            response = textract_client.start_document_text_detection(
                DocumentLocation={'S3Object': {'Bucket': input_bucket_name, 'Name': file_name}}
            )

            # Print the Textract response
            print(response)

            # Copy the output JSON to the output S3 bucket
            output_key = file_name.replace(".pdf", ".json")
            s3.copy_object(
                CopySource={'Bucket': input_bucket_name, 'Key': output_key},
                Bucket=output_bucket_name,
                Key=output_key
            )

if __name__ == "__main__":
    main()