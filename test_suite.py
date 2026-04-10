import os
import time
import json
from datetime import datetime
from services.worker_service import run_intent_job
from services.session_service import SessionService
from services.user_service import UserService

# Mock Telegram Helpers to prevent hanging/network calls during tests
import telegram_helpers
telegram_helpers.send_message = lambda *args, **kwargs: {"ok": True, "result": {"message_id": 12345}}
telegram_helpers.send_photo = lambda *args, **kwargs: {"ok": True, "result": {"message_id": 12346}}
telegram_helpers.edit_message = lambda *args, **kwargs: {"ok": True, "result": {"message_id": 12345}}
telegram_helpers.delete_message = lambda *args, **kwargs: {"ok": True}
telegram_helpers.answer_callback_query = lambda *args, **kwargs: True

# Fix for Windows console encoding (CP1252)
def safe_print(msg):
    try:
        print(msg)
    except Exception:
        print(str(msg).encode('ascii', 'ignore').decode('ascii'))

class BotTester:
    def __init__(self, chat_id="1878846631", username="Tester"):
        self.chat_id = chat_id
        self.username = username
        self.session_service = SessionService()
        self.user_service = UserService()
        
    def run_case(self, name, intent, input_text=""):
        safe_print(f"\n[TEST] Running: {name} (intent={intent}, text='{input_text}')")
        start = time.time()
        
        session = self.session_service.get_session(self.chat_id)
        user = self.user_service.get_user(self.chat_id)
        
        try:
            run_intent_job(
                intent=intent,
                chat_id=self.chat_id,
                username=self.username,
                input_text=input_text,
                session=session,
                user=user
            )
            status = "PASS"
        except Exception as e:
            safe_print(f"[TEST] FAILED: {e}")
            import traceback; traceback.print_exc()
            status = "FAIL"
        
        elapsed = time.time() - start
        safe_print(f"[TEST] Completed: {status} in {elapsed:.2f}s")
        return {"name": name, "status": status, "time": elapsed}

def run_integration_test():
    tester = BotTester()
    results = []
    
    # 0. Cleanup old session
    tester.session_service.reset_session(tester.chat_id)
    
    # 1. Start flow
    results.append(tester.run_case("Init Start", "start", "/start"))
    
    # 2. Simulate 8 questions flow (to trigger _finalize)
    steps = [
        ("Mood Selection", "q_mood_Happy"),
        ("Genre Multi-Select 1", "q_genre_Action"),
        ("Genre Multi-Select 2", "q_genre_Comedy"),
        ("Genre Done", "q_done_genre"),
        ("Language Selection", "q_language_English"),
        ("Era Selection", "q_era_2000s"),
        ("Context Selection", "q_context_Alone"),
        ("Time Selection", "q_time_Standard (2h)"),
        ("Avoid Input", "Horror, Blood"),
        ("Favorites/Final Step", "Inception, Christopher Nolan")
    ]
    
    for label, val in steps:
        results.append(tester.run_case(f"Q: {label}", "questioning", val))
    
    # 3. Test Interactions (Likes/Interests)
    results.append(tester.run_case("Like Interaction", "like", "like_tt0133093")) # The Matrix ID
    
    # 4. Test More Recs
    results.append(tester.run_case("More Recs Iteration", "questioning", "q_more_recs"))

    # 5. Check Admin Metrics
    results.append(tester.run_case("Admin Stats Check", "admin_stats"))
    
    safe_print("\n" + "="*40)
    safe_print(" INTEGRATION TEST REPORT ")
    safe_print("="*40)
    passed = len([r for r in results if r["status"] == "PASS"])
    safe_print(f"Summary: {passed}/{len(results)} Passed")
    
    for r in results:
        safe_print(f"- {r['name']}: {r['status']} ({r['time']:.2f}s)")

if __name__ == "__main__":
    run_integration_test()
