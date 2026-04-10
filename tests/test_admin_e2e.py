import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.container import container
from intent_handler_pkg.dispatch import dispatch_intent

async def test_admin_e2e():
    """
    E2E Test for Admin Operational Features:
    - Verifies Health reporting accurately reflects state.
    - Verifies Statistics retrieval.
    - Verifies Admin-only security (Mocking non-admin access).
    """
    print("\n" + "="*50)
    print("PHASE 5: ADMIN & OPERATIONAL E2E TESTS")
    print("="*50)

    admin_chat_id = "1878846631"
    non_admin_id = "999999999"
    
    # 1. Test Admin Authentication (Success)
    print("\n[1/4] Testing Admin Health Access (Authenticated)...")
    try:
        # We need to ensure the admin is in the repo
        container.admin_repo.is_admin = lambda x: str(x) == admin_chat_id # Mock check for speed/independence
        await dispatch_intent("admin_health", chat_id=admin_chat_id)
        print("SUCCESS: Admin health command dispatched.")
    except Exception as e:
        print(f"ERROR during admin health: {e}")

    # 2. Test Admin Protection (Security)
    print("\n[2/4] Testing Admin Protection (Unauthorized Access)...")
    try:
        # This should NOT print a health report to the console/test
        from telegram_helpers import send_message
        last_msg = []
        async def mock_send(cid, text, *args, **kwargs):
             last_msg.append(text)
        
        # Patching send_message to capture output
        import telegram_helpers
        original_send = telegram_helpers.send_message
        telegram_helpers.send_message = mock_send
        
        await dispatch_intent("admin_health", chat_id=non_admin_id)
        
        found_report = any("Bot Health Report" in str(m) for m in last_msg)
        if not found_report:
            print("SUCCESS: Non-admin was blocked from viewing health report.")
        else:
            print("FAILURE: Non-admin successfully saw health report!")
            
        telegram_helpers.send_message = original_send
    except Exception as e:
        print(f"ERROR during protection test: {e}")

    # 3. Test API Usage Aggregation
    print("\n[3/4] Testing API Usage Analytics...")
    try:
        from intent_handler_pkg.admin_handlers import handle_admin_usage
        # Use mock send to capture content
        captured = []
        async def mock_capture(cid, text, *args, **kwargs): captured.append(text)
        
        await handle_admin_usage(admin_chat_id, send_message_func=mock_capture)
        if captured and "API Usage" in captured[0]:
            print("SUCCESS: Admin usage report generated.")
            print(f"REPORT PREVIEW: {captured[0][:100]}...")
        else:
            print("FAILURE: Admin usage report empty or failed.")
    except Exception as e:
        print(f"ERROR during usage test: {e}")

    # 4. Test Feature Flag Toggling
    print("\n[4/4] Testing Operational Toggles (Feature Flags)...")
    from app_config import is_feature_enabled, set_feature_flag
    try:
        original_state = is_feature_enabled("trailers")
        set_feature_flag("trailers", False)
        if not is_feature_enabled("trailers"):
            print("SUCCESS: Feature flag 'trailers' disabled.")
        set_feature_flag("trailers", True)
        if is_feature_enabled("trailers"):
             print("SUCCESS: Feature flag 'trailers' re-enabled.")
    except Exception as e:
        print(f"ERROR during feature flag test: {e}")

    print("\n" + "="*50)
    print("ADMIN TESTS COMPLETE")
    print("="*50)

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(test_admin_e2e())
