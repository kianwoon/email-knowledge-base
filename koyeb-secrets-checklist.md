# Koyeb Secrets Checklist

Based on the .koyeb.yml configuration, ensure the following secrets are properly set in your Koyeb dashboard:

## Required Secrets

- [ ] `MS_CLIENT_SECRET` - Microsoft OAuth client secret
- [ ] `JWT_SECRET` - Secret key for JWT token signing
- [ ] `MS_AUTH_BASE_URL` - Microsoft Auth base URL
- [ ] `MS_SCOPE` - Microsoft OAuth scope string
- [ ] `MS_GRAPH_BASE_URL` - Microsoft Graph API base URL
- [ ] `JWT_ALGORITHM` - Algorithm for JWT (usually "HS256")
- [ ] `JWT_EXPIRATION` - JWT token expiration time in seconds
- [ ] `OPENAI_API_KEY` - OpenAI API key
- [ ] `EMBEDDING_MODEL` - Vector embedding model name
- [ ] `EMBEDDING_DIMENSION` - Embedding dimension size
- [ ] `QDRANT_URL` - Qdrant vector database URL
- [ ] `QDRANT_API_KEY` - Qdrant API key
- [ ] `QDRANT_COLLECTION_NAME` - Qdrant collection name
- [ ] `MAX_PREVIEW_EMAILS` - Maximum emails to preview
- [ ] `APP_AWS_ACCESS_KEY_ID` - AWS access key
- [ ] `APP_AWS_SECRET_ACCESS_KEY` - AWS secret key
- [ ] `AWS_REGION` - AWS region
- [ ] `EXTERNAL_ANALYSIS_URL` - External analysis service URL
- [ ] `EXTERNAL_ANALYSIS_API_KEY` - External analysis API key
- [ ] `CORS_ALLOWED_ORIGINS` - CORS allowed origins
- [ ] `WEBHOOK_PREFIX` - Webhook prefix
- [ ] `EXTERNAL_WEBHOOK_BASE_URL` - External webhook base URL
- [ ] `ALLOWED_REDIRECT_DOMAINS` - Allowed redirect domains
- [ ] `ENCRYPTION_KEY` - Encryption key for sensitive data
- [ ] `SQLALCHEMY_DATABASE_URI` - Database connection string
- [ ] `CELERY_BROKER_URL` - Redis connection for Celery broker
- [ ] `CELERY_RESULT_BACKEND` - Redis connection for Celery results

## How to Add Secrets in Koyeb

1. Log in to the Koyeb console: https://app.koyeb.com/
2. Navigate to "Secrets" in the left menu
3. Click "Create Secret"
4. For each secret:
   - Set the secret name exactly as listed above
   - Enter the secret value
   - Click "Create"
5. After adding all secrets, redeploy your application

## Troubleshooting Missing Secrets

If your deployment fails with "Could not retrieve one or more Secrets", review:

1. Check for typos in secret names
2. Verify all secrets are created in the same Koyeb organization/project
3. Ensure the Koyeb service has access to the secrets
4. Use the Koyeb CLI to verify secrets existence:
   ```
   koyeb secrets list
   ```

## Checking Service Logs

To view detailed logs after deployment:
```
koyeb service logs <service-name>
``` 