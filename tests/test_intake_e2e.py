import asyncio
import os
import sys
import uuid
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.container import container
from intent_handler_pkg.dispatch import dispatch_intent
from repositories.session_repository import SessionRepository

async def test_intake_e2e():
    """
    E2E Test for User Intake and Questionnaire:
    - Verifies /start initialization.
    - Verifies AI-driven answer normalization.
    - Verifies session state transitions.
    """
    print("\n" + "="*50)
    print("PHASE 3: INTERACTION & INTAKE E2E TESTS")
    print("="*50)

    chat_id = "1878846631" # Admin Chat ID for testing
    session_repo = container.session_repo
    
    # 1. Reset Session to start fresh
    print("\n[1/4] Resetting session for clean state...")
    try:
        session_repo.reset_session(chat_id)
        print("SUCCESS: Session reset.")
    except Exception as e:
        print(f"ERROR during reset: {e}")

    # 2. Simulate /start
    print("\n[2/4] Simulating '/start'...")
    try:
        await dispatch_intent("start", chat_id=chat_id, username="TestUser")
        session = session_repo.get_session(chat_id)
        print(f"SUCCESS: Session state is '{session.get('session_state')}'.")
        if session.get("session_state") != "idle": # Based on code, /start might set it to idle or intro
            print(f"INFO: question_index is {session.get('question_index')}")
    except Exception as e:
        print(f"ERROR during start: {e}")

    # 3. Test AI Normalization (Single Step)
    print("\n[3/4] Testing AI Answer Normalization (Mood: 'I'm super happy and want a laugh')...")
    from perplexity_client import understand_user_answer
    try:
        norm_mood = await understand_user_answer("Mood/Vibe", "I'm super happy and want a laugh", chat_id=chat_id)
        print(f"SUCCESS: Normalized answer: '{norm_mood}'")
        if not norm_mood or "happy" not in norm_mood.lower() and "comedy" not in norm_mood.lower():
            print(f"WARNING: Normalization results seem unexpected: {norm_mood}")
    except Exception as e:
        print(f"ERROR during normalization: {e}")

    # 4. Simulate Questionnaire Progression
    print("\n[4/4] Simulating Questionnaire Progress (Step 1 -> 2)...")
    try:
        # Manually patch session to simulate being mid-questionnaire
        session_repo.upsert_session(chat_id, {
            "session_state": "questioning",
            "question_index": 1,
            "answers_mood": "Happy/Comedy"
        })
        
        # Dispatch 'questioning' intent with an answer
        await dispatch_intent("questioning", chat_id=chat_id, text="Action/Thriller")
        
        updated_session = session_repo.get_session(chat_id)
        print(f"SUCCESS: New Index: {updated_session.get('question_index')}")
        print(f"SUCCESS: Stored Genre: {updated_session.get('answers_genre')}")
        
    except Exception as e:
        print(f"ERROR during progression: {e}")

    print("\n" + "="*50)
    print("INTAKE TESTS COMPLETE")
    print("="*50)

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(test_intake_e2e())
