from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_kms as kms,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_iam as iam,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct

class CloudFrontS3Stack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Crear la llave KMS con alias
        kms_key = kms.Key(
            self, "S3KMSKey",
            description="KMS Key for S3 bucket encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Crear el alias para la llave KMS
        kms_alias = kms.Alias(
            self, "S3KMSKeyAlias",
            alias_name="alias/s3",
            target_key=kms_key
        )

        # Crear el bucket S3 privado con cifrado KMS
        s3_bucket = s3.Bucket(
            self, "S3Bucket",
            bucket_name="bucket-prueba-dummy-oac",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=kms_key,
            bucket_key_enabled=True,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Crear Origin Access Control (OAC)
        origin_access_control = cloudfront.CfnOriginAccessControl(
            self, "OriginAccessControl",
            origin_access_control_config=cloudfront.CfnOriginAccessControl.OriginAccessControlConfigProperty(
                name="S3-OAC",
                origin_access_control_origin_type="s3",
                signing_behavior="always",
                signing_protocol="sigv4"
            )
        )

        # Crear la distribución de CloudFront
        distribution = cloudfront.Distribution(
            self, "CloudFrontDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    bucket=s3_bucket,
                    origin_access_identity=None  # No usamos OAI, usaremos OAC
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN
            ),
            default_root_object="index.html",
            comment="CloudFront distribution for S3 bucket with OAC"
        )

        # Obtener el CFN distribution para configurar OAC
        cfn_distribution = distribution.node.default_child
        
        # Configurar OAC en lugar de OAI
        cfn_distribution.add_property_override(
            "DistributionConfig.Origins.0.S3OriginConfig.OriginAccessIdentity", ""
        )
        cfn_distribution.add_property_override(
            "DistributionConfig.Origins.0.OriginAccessControlId", 
            origin_access_control.attr_id
        )

        # Crear políticas separadas usando CfnResource para evitar dependencias circulares
        
        # Política para el bucket S3 que permite acceso a CloudFront
        s3_bucket_policy = s3.CfnBucketPolicy(
            self, "S3BucketPolicy",
            bucket=s3_bucket.bucket_name,
            policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "cloudfront.amazonaws.com"
                        },
                        "Action": "s3:GetObject",
                        "Resource": f"{s3_bucket.bucket_arn}/*",
                        "Condition": {
                            "StringEquals": {
                                "AWS:SourceArn": f"arn:aws:cloudfront::{self.account}:distribution/{distribution.distribution_id}"
                            }
                        }
                    }
                ]
            }
        )
        
        # Asegurar que la política se cree después de la distribución
        s3_bucket_policy.add_dependency(cfn_distribution)

        # Para KMS, usar una política más permisiva sin referencia circular
        kms_policy_statement = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
            actions=[
                "kms:Decrypt",
                "kms:GenerateDataKey"
            ],
            resources=["*"],
            conditions={
                "StringLike": {
                    "AWS:SourceArn": f"arn:aws:cloudfront::{self.account}:distribution/*"
                }
            }
        )

        # Agregar la política a la llave KMS (sin referencia específica a la distribución)
        kms_key.add_to_resource_policy(kms_policy_statement)

        # Outputs
        CfnOutput(
            self, "BucketName",
            value=s3_bucket.bucket_name,
            description="Name of the S3 bucket"
        )

        CfnOutput(
            self, "KMSKeyId",
            value=kms_key.key_id,
            description="KMS Key ID"
        )

        CfnOutput(
            self, "KMSKeyAlias",
            value=kms_alias.alias_name,
            description="KMS Key Alias"
        )

        CfnOutput(
            self, "CloudFrontDistributionId",
            value=distribution.distribution_id,
            description="CloudFront Distribution ID"
        )

        CfnOutput(
            self, "CloudFrontDomainName",
            value=distribution.distribution_domain_name,
            description="CloudFront Distribution Domain Name"
        )

        CfnOutput(
            self, "OriginAccessControlId",
            value=origin_access_control.attr_id,
            description="Origin Access Control ID"
        )
