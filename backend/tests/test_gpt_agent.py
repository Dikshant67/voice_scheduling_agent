from openai import AzureOpenAI
from datetime import datetime
# ✅ Setup client
import os
from openai import AzureOpenAI
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
# ✅ Your deployment name in Azure
deployment_name = "gpt-4o"  # Replace with the actual deployed name

# ✅ Function to query GPT
def extract_meeting_info(prompt_text):
    today = datetime.now().strftime('%Y-%m-%d')  # 👈 Get today’s date
    
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a meeting assistant. Today's date is {today}. "
                        "Extract meeting details from the user's message and respond with only JSON:\n"
                        "{'intent': 'schedule_meeting', 'title': 'Team Sync', 'date': '2025-08-09', 'time': '14:00'}\n"
                        
                    )
                },
                {"role": "user", "content": prompt_text}
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Error: {e}"

if __name__ == "__main__":
    test_input = "Hey, please schedule a meeting with John on day after tomorrow at 4 PM about our AI project."
    print("📥 Input:", test_input)
    result = extract_meeting_info(test_input)
    print("📤 GPT Output:\n", result)