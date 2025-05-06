            logger.debug(f"Attempting to refresh MS token for user '{email}' using refresh token.")
            # Attempt to acquire token using the refresh token, passing timeout via kwargs
            result = await run_in_threadpool(
                _msal_app.acquire_token_by_refresh_token,
                refresh_token=decrypted_refresh_token,
                scopes=settings.MS_SCOPE_STR.split(),
                # Pass timeout as a keyword argument recognised by MSAL/requests
                timeout=20  
            )
            # --- Log the raw result for debugging --- 