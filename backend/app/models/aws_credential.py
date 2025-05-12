"""
This file re-exports the AwsCredential model from app.db.models 
to maintain import compatibility with existing code.
"""

# Re-export the model from the db.models package
from app.db.models.aws_credential import AwsCredential 