from google_auth_oauthlib.flow import InstalledAppFlow
import pickle

# Calendar scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

flow = InstalledAppFlow.from_client_secrets_file(
    'credentials.json', SCOPES)
creds = flow.run_local_server(port=0)

# Save the token for later use
with open('token.pickle', 'wb') as token:
    pickle.dump(creds, token)

print("✅ Authentication complete. Token saved to token.pickle.")