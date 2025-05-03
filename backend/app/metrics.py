# backend/app/metrics.py
import logging
from prometheus_client import Counter

logger = logging.getLogger(__name__)

# Define counters for specific gateway actions
COLUMN_BLOCKS = Counter(
    "column_blocks_total",
    "Count of column fields blocked from results due to token policy",
    ["token_id", "route"]
)
ATTACHMENT_REDACTIONS = Counter(
    "attachment_redactions_total",
    "Count of result attachments redacted due to token policy",
    ["token_id", "route"]
)

logger.info("Prometheus counters (COLUMN_BLOCKS, ATTACHMENT_REDACTIONS) defined.") 