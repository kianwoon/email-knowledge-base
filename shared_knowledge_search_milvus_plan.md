# Revised Plan: /shared-knowledge/search Endpoint (Milvus-Only RAG Source)

**Date:** 2024-08-14

**Status:** Proposed

## Goal

Provide a robust, secure, and well-documented API endpoint (`GET /api/v1/shared-knowledge/search`) for external users to retrieve permission-scoped context chunks *exclusively from the Milvus vector database* using a shared token. This endpoint is intended to be integrated as a retrieval source into external RAG (Retrieval-Augmented Generation) chatbots.

## Baseline (Current Implementation)

Based on the code in `backend/app/routes/shared_knowledge.py`:

*   **Functionality:** Implements a Milvus-only query flow.
*   **Authentication:** Uses `Authorization: Bearer <token>` validated by the `get_validated_token` dependency.
*   **Tenancy:** Targets the Milvus collection associated with the token owner (`token.owner_email`).
*   **Core Logic:** Embeds the query, applies Milvus filters based on token rules, performs semantic search (`search_milvus_knowledge`), and reranks results (`rerank_results`).
*   **Permission Enforcement:**
    *   Row-level Filters: Applied via Milvus filter expression derived from `allow_rules`/`deny_rules`.
    *   Column Projection: Filters the `metadata` field based on `token.allow_columns`.
    *   Attachment Filtering: Removes known attachment keys from `metadata` if `token.allow_attachments` is false.
    *   Result Limiting: Respects `min(query_limit, token.row_limit)`.
*   **Output:** Returns `List[Dict[str, Any]]` containing `id`, `score`, and filtered `metadata`.
*   **Observability:** Includes Prometheus counters for permission enforcement actions.

## Required Enhancements

1.  **Security Validation (Highest Priority):**
    *   **Verify `get_validated_token`:** Thoroughly review `app.dependencies.auth.get_validated_token` for secure token extraction, hash validation (bcrypt vs `hashed_token`), `is_active` check, `expiry` check, and optional `audience` checks.
    *   **Verify `token_crud.create_milvus_filter_from_token`:** Review the logic translating `allow_rules`/`deny_rules` (JSONB) into a secure Milvus filter expression, preventing injection or unintended exposure.

2.  **API Definition & Documentation (Critical for External Users):**
    *   **Define Explicit Response Model:** Create a Pydantic model (e.g., `SharedMilvusResult`) with fields like `id: str`, `score: float`, `metadata: Dict[str, Any]` and use it in the endpoint signature (`response_model=List[SharedMilvusResult]`).
    *   **Detailed Docstrings:** Enhance the endpoint's docstring for clear auto-generated OpenAPI documentation, covering purpose, auth, parameters, effects of token permissions on the response, status codes, and response structure.
    *   **Generate/Review OpenAPI Spec:** Ensure `/docs` provides accurate and usable documentation for API consumers.

3.  **Reranking Review:**
    *   Briefly review the `rerank_results` function for correctness and suitability.

4.  **Error Handling:**
    *   Refine error messages and status codes (401 vs. 403) for different failure scenarios (invalid token, expired, inactive, forbidden) without leaking internal details.

5.  **Comprehensive Testing:**
    *   Implement integration tests covering various token states (valid, invalid, active, inactive, expired), permission combinations (`allow_columns`, `allow_attachments`, `row_limit`, `allow/deny_rules`), audience restrictions (if applicable), and edge cases.

6.  **Acknowledge Limitations:**
    *   Add code comments and potentially API documentation explicitly stating that this endpoint **only searches Milvus** and does not include data from Iceberg in this phase.

## Out of Scope (Deferred)

*   Integration with Iceberg catalog for retrieving structured data.
*   Combining results from Milvus and Iceberg.

## Next Step

Begin implementation by reviewing the security-critical dependencies:
1.  `app.dependencies.auth.get_validated_token`
2.  `app.crud.token_crud.create_milvus_filter_from_token` 