# epsi-next-poc
External Environment - S3 - Lambda - Amazaon Textract - S3 - External Environment

## Pre-requisite
Set your environment variables
```bash
export AWSAccessKeyID=`AWS Access Key ID`
export AWSSecretAccessKey=`AWS Secret Access Key`
export AWSRegion=`AWS Region`
```

## Build Docker Image
```bash
docker build -t epsi-next-poc .
```

## Run Docker Container
```bash
docker run --rm -it -e AWSAccessKeyID=$AWSAccessKeyID -e AWSSecretAccessKey=$AWSSecretAccessKey -e AWSRegion=$AWSRegion -v `/local/directory/`:`/target/directory/` epsi-next-poc /bin/bash
```

## Run the Python Script
```bash
python epsi-text-extraction.py `/target/directory/file.pdf`
```

Check the inbound-pdfs and outbound-jsons buckets