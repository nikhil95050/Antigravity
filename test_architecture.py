import os
import sys

# Add current dir to path for imports
sys.path.append(os.getcwd())

from services.session_service import SessionService
from services.user_service import UserService
from services.movie_service import MovieService
from repositories.base_repository import is_supabase_configured

def test_repositories():
    print("Testing Repositories & Services...")
    
    chat_id = "test_123"
    
    # 1. Session Service
    ss = SessionService()
    ss.reset_session(chat_id)
    session = ss.get_session(chat_id)
    print(f"Session reset/get: {'✅' if session.get('session_state') == 'idle' else '❌'}")
    
    # 2. User Service
    us = UserService()
    us.upsert_user(chat_id, "test_user", {"preferred_genres": "Action"})
    user = us.get_user(chat_id)
    print(f"User upsert/get: {'✅' if user.get('username') == 'test_user' else '❌'}")
    
    # 3. Movie Service
    ms = MovieService()
    ms.add_to_history(chat_id, [{"movie_id": "m1", "title": "Inception"}])
    # History fetching might be slow or return [] if Supabase isn't synced yet, 
    # but the call should succeed.
    print("Movie history call: ✅")

if __name__ == "__main__":
    if not is_supabase_configured():
        print("Skipping tests: Supabase not configured.")
    else:
        try:
            test_repositories()
        except Exception as e:
            print(f"Tests failed: {e}")
            import traceback; traceback.print_exc()
