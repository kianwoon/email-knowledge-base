# API Keys Migration Guide

This directory contains scripts to migrate the OpenAI API key storage from a single column in the user table to a dedicated `api_keys` table. This improves:

1. **Security**: Dedicated table for sensitive credentials
2. **Flexibility**: Support for multiple API key providers (OpenAI, Anthropic, etc.)
3. **Features**: Track usage, multiple keys per user, etc.
4. **Authentication reliability**: Fix issues with API keys disappearing on logout/login

## Migration Process

The migration has three phases, each with a dedicated script:

### Phase 1: Create the new table and migrate data

Run:
```
python -m backend.migrations.add_api_keys_table
```

This script:
- Creates the new `api_keys` table if it doesn't exist
- Migrates existing API keys from the `users.openai_api_key` column to the new table
- Logs results of the migration

### Phase 2: Dual write period

After running Phase 1, both storage methods will be active:
- New API keys are written to both the old column and the new table
- Keys are read first from the new table, falling back to the old column
- This ensures backward compatibility during the transition

During this period, you should verify the migration by:
- Checking that users can still use their existing API keys
- Ensuring new API keys are correctly stored
- Confirming that API keys remain after logout/login cycles

### Phase 3: Remove the old column

Once you're satisfied with the migration, run:
```
python -m backend.migrations.remove_openai_api_key
```

This script:
- Performs safety checks to ensure data has been properly migrated
- Asks for explicit confirmation before proceeding
- Removes the `openai_api_key` column from the `users` table

## API Changes

The API endpoints remain compatible with the existing frontend:
- `/user/api-key` (GET/POST/DELETE) work as before
- New endpoint `/user/api-keys` (GET) returns information about all API keys
- New endpoint `/user/migrate-api-keys` can be used to manually trigger migration

## Reverting (if needed)

If issues are discovered, the system will continue working with the dual storage approach. To completely revert, you would need to:

1. Run a custom script to copy keys back from the `api_keys` table to the `users.openai_api_key` column
2. Update the API endpoint implementations to use only the old column
3. Drop the `api_keys` table

## Implementation Details

Key changes:
- New `api_key.py` model file defining the API keys table and relationships
- New `api_key_crud.py` with CRUD operations for the new table
- Updated `auth.py` to fetch keys from the new table first
- Updated `user.py` routes to support both old and new storage methods
- Auto-migration logic to move keys when detected in the old location

## Troubleshooting

If users report missing API keys:
- Check logs for errors in key decryption or migration
- Run the manual migration endpoint `/user/migrate-api-keys`
- Verify proper encryption key configuration in `.env` file 