# test_groq_direct.py
import os
from dotenv import load_dotenv
from groq import Groq, AuthenticationError, APIConnectionError, APIError

# Load .env manually for this test
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

print(f"Key loaded: {'Yes' if api_key else 'No'}")
print(f"Key length: {len(api_key) if api_key else 0}")
print(f"Key preview: {api_key[:10]}...{api_key[-4:] if api_key else 'N/A'}")

try:
    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello in one word."}
        ],
        temperature=0.3,
        max_tokens=10
    )
    print(f"\n✅ SUCCESS! Response: {completion.choices[0].message.content}")
except AuthenticationError as e:
    print(f"\n❌ AUTH ERROR: {e}")
except APIConnectionError as e:
    print(f"\n❌ CONNECTION ERROR: {e}")
except APIError as e:
    print(f"\n❌ API ERROR: {e}")
except Exception as e:
    print(f"\n❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")