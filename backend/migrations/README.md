# Database Migrations

This directory contains migration scripts to update the database schema over time.

## Running Migrations

To run a migration script, use the Python interpreter from the project's root:

```bash
# From the backend directory
python -m migrations.add_openai_api_key
```

## Available Migrations

- `add_openai_api_key.py`: Adds the `openai_api_key` column to the `users` table for storing user-specific OpenAI API keys.

## Creating New Migrations

When creating a new migration:

1. Create a new Python file in this directory with a descriptive name
2. The script should be able to run safely multiple times (check if changes already exist)
3. Add error handling and logging
4. Document the migration in this README 