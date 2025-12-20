
import os
import time
import uuid
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

# Configuration
BASE_URL = "http://localhost:3000"
BACKEND_URL = "http://localhost:8000"
HEADLESS = True  
TIMEOUT = 45000 # Increased timeout for vector processing

def test_chat_and_verify_answer():
    """
    End-to-End UI QA Test:
    1. Open the application
    2. Upload a text file with specific content
    3. Select the file for chat
    4. Ask a question about the content
    5. Verify the answer matches the content (RAG verification)
    """
    print(f"🚀 Starting E2E QA Test against {BASE_URL}")
    
    # Create a unique file for testing
    run_id = uuid.uuid4().hex[:8]
    test_filename = f"qa_test_{run_id}.txt"
    magic_word = f"XYZZY{run_id}"
    test_content = f"This is a QA automation test file. The special secret code is {magic_word}. Please returned this code when asked."
    
    file_path = Path.cwd() / test_filename
    file_path.write_text(test_content)
    print(f"📄 Created test file: {test_filename} with secret: {magic_word}")

    try:
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=HEADLESS, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = browser.new_context()
            page = context.new_page()
            
            # Capture console logs
            page.on("console", lambda msg: print(f"BRWSR: {msg.text}"))
            
            # 1. Open Application
            print("🌐 Navigating to home page...")
            page.goto(BASE_URL)
            
            # 2. Upload File
            print("📤 Uploading file...")
            file_input = page.locator("input[type='file']")
            
            # Wait for input (it might be hidden but present)
            if not file_input.is_visible() and not file_input.is_hidden():
                 file_input.wait_for(state="attached", timeout=10000)

            file_input.set_input_files(str(file_path))
            
            # 3. Wait for file to appear in sources list
            # Note: Backend now appends a suffix to the filename for uniqueness
            # So we search for the stem (e.g. "qa_test_xyz" in "qa_test_xyz_suffix.txt")
            search_term = file_path.stem 
            print(f"👀 Waiting for '{search_term}' to appear in sources list...")
            
            # Locator for the source card
            source_card = page.locator(".source-file-card", has_text=search_term)
            source_card.wait_for(timeout=30000)
            print("✅ File found in UI list!")

            # 4. Select the source for chat
            print("✅ Selecting source for chat...")
            # Find the checkbox within this specific card
            checkbox = source_card.locator("input[type='checkbox']")
            
            # Check if already checked
            if not checkbox.is_checked():
                checkbox.check()
                print("☑️ Checked source checkbox")
            else:
                print("☑️ Source already checked")
            
            # Click the source title to open the Guide view
            print("👆 Clicking source title to open Guide...")
            source_card.click()

            # Wait for Start Chat button in the Guide view
            print("⏳ Waiting for Start Chat button...")
            start_chat_btn = page.locator("button[data-testid='start-chat-btn']")
            try:
                start_chat_btn.wait_for(timeout=10000)
                start_chat_btn.click()
                print("💬 Switched to Chat view")
            except Exception: 
                print("⚠️ Start chat button not found, maybe already in chat view?")
                
            # 5. Ask Question
            print("💬 Asking question...")
            question = "What is the special secret code?"
            
            # Type into chat input
            chat_input = page.locator("textarea[data-testid='chat-input']")
            chat_input.wait_for(state="visible", timeout=10000)
            chat_input.fill(question)
            
            # Click send
            send_btn = page.locator("button[data-testid='send-button']")
            send_btn.click()
            
            # 6. Verify Answer
            print("⏳ Waiting for answer...")
            
            # We look for the last message from assistant
            # Use a more specific waiter. We expect a new message bubble to appear.
            # The answer should contain our magic word.
            
            # Wait for assistant message containing the magic word
            # This implicitly validates that the RAG worked and retrieved the correct chunk
            try:
                # Allow time for processing (ingestion + LLM generation)
                expect(page.locator("div[data-testid^='message-']").last).to_contain_text(magic_word, timeout=45000)
                print(f"✅ Found magic word '{magic_word}' in chat response!")
            except AssertionError as e:
                print(f"❌ Magic word '{magic_word}' NOT found in response.")
                print("Dumping last few messages:")
                messages = page.locator("div[data-testid^='message-']").all_text_contents()
                for m in messages[-3:]:
                    print(f"-- {m}")
                raise e

            print("✅ Test Passed: RAG QA verification successful.")
            
    except Exception as e:
        print(f"💥 Test Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Cleanup
        if file_path.exists():
            file_path.unlink()
        print("🧹 Cleanup complete")

if __name__ == "__main__":
    test_chat_and_verify_answer()
