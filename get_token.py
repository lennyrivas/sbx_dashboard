from google_auth_oauthlib.flow import InstalledAppFlow

def get_refresh_token():
    # Указываем права доступа к Google Drive
    SCOPES = ['https://www.googleapis.com/auth/drive']

    # Запускаем процесс авторизации
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secret.json', SCOPES)

    # Откроется браузер для входа в аккаунт
    creds = flow.run_local_server(port=0)

    print("\n" + "="*50)
    print("✅ SKOPIUJ PONIŻSZE DANE DO PLIKU .streamlit/secrets.toml")
    print("="*50)
    print("[google_oauth]")
    print(f'refresh_token = "{creds.refresh_token}"')
    print(f'client_id = "{creds.client_id}"')
    print(f'client_secret = "{creds.client_secret}"')
    print("="*50)

if __name__ == "__main__":
    get_refresh_token()
