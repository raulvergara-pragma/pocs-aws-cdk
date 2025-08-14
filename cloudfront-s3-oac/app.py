#!/usr/bin/env python3
import os
import aws_cdk as cdk
from cloudfront_s3_stack import CloudFrontS3Stack

app = cdk.App()
CloudFrontS3Stack(app, "CloudFrontS3Stack",
    env=cdk.Environment(
        account=os.getenv('ACCOUNT_ID_ENV_VAR'),
        region=os.getenv('us-east-1')
    )
)

app.synth()
