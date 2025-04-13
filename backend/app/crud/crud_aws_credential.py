from sqlalchemy.orm import Session
from app.models.aws_credential import AwsCredential
from app.schemas.s3 import S3ConfigCreate


def get_aws_credential_by_user_email(db: Session, *, user_email: str) -> AwsCredential | None:
    """Gets AWS credential configuration for a specific user by email."""
    return db.query(AwsCredential).filter(AwsCredential.user_email == user_email).first()

def create_or_update_aws_credential(db: Session, *, user_email: str, config_in: S3ConfigCreate) -> AwsCredential:
    """Creates a new AWS credential config or updates an existing one for a user."""
    db_obj = get_aws_credential_by_user_email(db, user_email=user_email)
    if db_obj:
        # Update existing
        db_obj.role_arn = config_in.role_arn
    else:
        # Create new
        db_obj = AwsCredential(
            user_email=user_email,
            role_arn=config_in.role_arn
        )
        db.add(db_obj)

    db.commit()
    db.refresh(db_obj)
    return db_obj

def remove_aws_credential(db: Session, *, user_email: str) -> AwsCredential | None:
    """Removes the AWS credential configuration for a user by email."""
    db_obj = get_aws_credential_by_user_email(db, user_email=user_email)
    if db_obj:
        db.delete(db_obj)
        db.commit()
    return db_obj 