"""
DynamoDB Storage Backend
Implements chat session storage using DynamoDB for scalable session management
"""

from typing import List, Optional
from datetime import datetime, timezone
import uuid
import boto3
from botocore.exceptions import ClientError

from backend.config import config
from backend.logger import get_logger
from backend.services.storage.base import BaseStorageBackend
from backend.services.models import ChatSession, QuizResult

logger = get_logger(__name__)


class DynamoDBStorageBackend(BaseStorageBackend):
    """DynamoDB implementation for chat session storage"""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        region_name: str = "us-east-1",
        table_name: str = "smart-tutor-chat-sessions",
    ):
        """
        Initialize DynamoDB client

        Args:
            endpoint_url: DynamoDB endpoint (use http://localhost:8001 for local)
            region_name: AWS region
            table_name: DynamoDB table name
        """
        self.table_name = table_name
        self.region_name = region_name

        # Configure boto3 client
        client_config = {
            "region_name": region_name,
        }

        # For local DynamoDB
        if endpoint_url:
            client_config["endpoint_url"] = endpoint_url
            # Use dummy credentials for local DynamoDB
            client_config["aws_access_key_id"] = "dummy"
            client_config["aws_secret_access_key"] = "dummy"
        else:
            # For production, use real AWS credentials
            if config.AWS_ACCESS_KEY_ID and config.AWS_SECRET_ACCESS_KEY:
                client_config["aws_access_key_id"] = config.AWS_ACCESS_KEY_ID
                client_config["aws_secret_access_key"] = config.AWS_SECRET_ACCESS_KEY

        self.dynamodb = boto3.resource('dynamodb', **client_config)
        self.table = self.dynamodb.Table(table_name)

        # Create table if it doesn't exist (for local development)
        if endpoint_url:
            self._ensure_table_exists()

        logger.info(f"DynamoDB storage backend initialized (table: {table_name})")

    def _ensure_table_exists(self):
        """Create DynamoDB table if it doesn't exist (local development only)"""
        try:
            # Check if table exists
            self.table.load()
            logger.info(f"DynamoDB table '{self.table_name}' already exists")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # Create table
                logger.info(f"Creating DynamoDB table '{self.table_name}'...")

                table = self.dynamodb.create_table(
                    TableName=self.table_name,
                    KeySchema=[
                        {'AttributeName': 'user_id', 'KeyType': 'HASH'},  # Partition key
                        {'AttributeName': 'session_id', 'KeyType': 'RANGE'}  # Sort key
                    ],
                    AttributeDefinitions=[
                        {'AttributeName': 'user_id', 'AttributeType': 'S'},
                        {'AttributeName': 'session_id', 'AttributeType': 'S'},
                    ],
                    BillingMode='PAY_PER_REQUEST',  # On-demand billing
                )

                # Wait for table to be created
                table.wait_until_exists()
                logger.info(f"DynamoDB table '{self.table_name}' created successfully")
            else:
                raise

    def list_chat_sessions(self, username: str) -> List[ChatSession]:
        """List all chat sessions for a user"""
        try:
            response = self.table.query(
                KeyConditionExpression='user_id = :user_id',
                ExpressionAttributeValues={':user_id': username},
                ScanIndexForward=False,  # Sort by session_id descending (newest first)
            )

            sessions = []
            for item in response.get('Items', []):
                session = ChatSession(
                    id=item['session_id'],
                    title=item.get('title', 'Untitled Session'),
                    messages=item.get('messages', []),
                    created_at=item.get('created_at'),
                    updated_at=item.get('updated_at'),
                )
                sessions.append(session)

            return sessions

        except Exception as e:
            logger.error(f"Error listing chat sessions for {username}: {e}")
            return []

    def load_chat_session(self, username: str, session_id: str) -> Optional[ChatSession]:
        """Load a specific chat session"""
        try:
            response = self.table.get_item(
                Key={
                    'user_id': username,
                    'session_id': session_id
                }
            )

            item = response.get('Item')
            if not item:
                return None

            session = ChatSession(
                id=item['session_id'],
                title=item.get('title', 'Untitled Session'),
                messages=item.get('messages', []),
                created_at=item.get('created_at'),
                updated_at=item.get('updated_at'),
            )

            return session

        except Exception as e:
            logger.error(f"Error loading chat session {session_id} for {username}: {e}")
            return None

    def save_chat_session(self, username: str, session: ChatSession) -> None:
        """Save or update a chat session"""
        try:
            now = datetime.now(timezone.utc).isoformat()

            # Prepare item
            item = {
                'user_id': username,
                'session_id': session.id or str(uuid.uuid4()),
                'title': session.title or 'Untitled Session',
                'messages': session.messages or [],
                'updated_at': now,
            }

            # Add created_at only for new sessions
            if not session.created_at:
                item['created_at'] = now

            # Save to DynamoDB
            self.table.put_item(Item=item)

            logger.debug(f"Saved chat session {item['session_id']} for {username}")

        except Exception as e:
            logger.error(f"Error saving chat session for {username}: {e}")
            raise

    def delete_chat_session(self, username: str, session_id: str) -> bool:
        """Delete a chat session"""
        try:
            self.table.delete_item(
                Key={
                    'user_id': username,
                    'session_id': session_id
                }
            )
            logger.info(f"Deleted chat session {session_id} for {username}")
            return True

        except Exception as e:
            logger.error(f"Error deleting chat session {session_id} for {username}: {e}")
            return False

    # These methods are not used by DynamoDB (users/quizzes are in PostgreSQL)
    def get_user(self, username: str) -> Optional[dict]:
        """Not implemented - users are in PostgreSQL"""
        logger.warning("User data should be retrieved from PostgreSQL, not DynamoDB")
        return None

    def create_user(self, username: str, password_hash: str, **extras) -> dict:
        """Not implemented - users are in PostgreSQL"""
        logger.warning("User data should be created in PostgreSQL, not DynamoDB")
        raise NotImplementedError("Use PostgreSQL for user management")

    def update_user(self, username: str, updates: dict) -> dict:
        """Not implemented - users are in PostgreSQL"""
        logger.warning("User data should be updated in PostgreSQL, not DynamoDB")
        raise NotImplementedError("Use PostgreSQL for user management")

    def save_quiz_result(self, result: QuizResult) -> None:
        """Not implemented - quiz results are in PostgreSQL"""
        logger.warning("Quiz results should be saved to PostgreSQL, not DynamoDB")
        raise NotImplementedError("Use PostgreSQL for quiz results")

    def list_quiz_results(self, username: str) -> List[QuizResult]:
        """Not implemented - quiz results are in PostgreSQL"""
        logger.warning("Quiz results should be retrieved from PostgreSQL, not DynamoDB")
        return []


# Singleton instance
_dynamodb_backend = None


def get_dynamodb_backend() -> DynamoDBStorageBackend:
    """Get singleton DynamoDB backend instance"""
    global _dynamodb_backend
    if _dynamodb_backend is None:
        endpoint_url = config.DYNAMODB_ENDPOINT if config.ENVIRONMENT != "production" else None
        region_name = config.DYNAMODB_REGION
        table_name = config.DYNAMODB_TABLE_CHAT_SESSIONS

        _dynamodb_backend = DynamoDBStorageBackend(
            endpoint_url=endpoint_url,
            region_name=region_name,
            table_name=table_name
        )
    return _dynamodb_backend
