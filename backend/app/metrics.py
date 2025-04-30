# backend/app/metrics.py
import logging
from prometheus_client import Counter

logger = logging.getLogger(__name__)

# Define counters for specific gateway actions
COLUMN_BLOCKS = Counter(
    "gateway_column_blocks_total", 
    "Total number of times columns were blocked based on token allow_columns list.",
    labelnames=["token_id", "route"] # Corrected: Use labelnames
)
ATTACHMENT_REDACTIONS = Counter(
    "gateway_attachment_redactions_total", 
    "Total number of times attachment data was redacted based on token allow_attachments flag.",
    labelnames=["token_id", "route"] # Corrected: Use labelnames
)

logger.info("Prometheus counters (COLUMN_BLOCKS, ATTACHMENT_REDACTIONS) defined.") 