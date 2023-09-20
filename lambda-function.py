import json
import boto3
import os

def lambda_ingester(event, context):
    s3 = boto3.client('s3')
    textract = boto3.client('textract')
    
    s3_inbound = 'inbound-pdfs'
    s3_outbound = 'outbound-jsons'

    for record in event['Records']:
        bucket_name = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']

        if object_key.lower().endswith(".pdf"):
            print(f"Processing: s3://{bucket_name}/{object_key}")

            # Send the PDF file to Textract
            response = textract.start_document_text_detection(
                DocumentLocation={'S3Object': {'Bucket': bucket_name, 'Name': object_key}}
            )
            
            # Specify the JobId of the Textract processing job
            job_id = response['JobId']
            
            while True:
                textract_object = textract.get_document_text_detection(JobId=job_id)
                status = textract_object['JobStatus']
                if status in ['SUCCEEDED', 'FAILED']:
                    break
            
            if status == 'SUCCEEDED':
                # Extract and concatenate the detected text
                extracted_text = ""
                
                for item in textract_object['Blocks']:
                    if item['BlockType'] == 'LINE':
                        extracted_text += item['Text'] + "\n"
                
                # Upload the extracted text to the outbound S3 bucket
                s3.put_object(
                    Bucket=s3_outbound,
                    Key=object_key.split('/')[-1].replace(' ', '_') + '.json',
                    Body=extracted_text.encode('utf-8')
                )
            else:
                print(f"Textract job status: {status}")