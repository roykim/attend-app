# attend-app

주일학교 출석 입력·통계 앱 (Streamlit + Google Sheets)

---

## 로컬 환경 설정 및 실행

### 1. Python 준비

- Python 3.9 이상 권장  
- 버전 확인: `python3 --version` 또는 `python --version`

### 2. 가상환경 만들기 (권장)

```bash
# 프로젝트 폴더로 이동
cd attend-app

# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
# macOS/Linux:
source venv/bin/activate
# Windows (CMD):
# venv\Scripts\activate.bat
# Windows (PowerShell):
# venv\Scripts\Activate.ps1
```

활성화되면 프롬프트 앞에 `(venv)` 가 붙습니다.

### 3. 의존성 설치 (requirements.txt)

```bash
pip install -r requirements.txt
```

설치되는 패키지: `streamlit`, `pandas`, `gspread`, `google-auth`, `plotly`

### 4. 시크릿 설정 (Google 시트 연동)

앱이 구글 시트에 접근하려면 서비스 계정 정보가 필요합니다.

1. **폴더 생성**
   ```bash
   mkdir -p .streamlit
   ```

2. **시크릿 파일 생성**  
   `.streamlit/secrets.toml` 파일을 만들고, 아래 형식으로 GCP 서비스 계정 정보를 넣습니다.

   ```toml
   [gcp_service_account]
   type = "service_account"
   project_id = "your-project-id"
   private_key_id = "..."
   private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
   client_email = "xxx@xxx.iam.gserviceaccount.com"
   client_id = "..."
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "..."

   # 앱 로그인·세션 암호화 (필수)
   encryption_key = "영문/숫자로 된 32자 이상 비밀 문자열"
   default_password = "최초 1회 로그인에 쓸 비밀번호"
   ```

   - Google Cloud Console에서 서비스 계정 JSON 키를 받은 뒤, 위 키 이름에 맞게 값을 채우면 됩니다.  
   - **주의:** `.streamlit/secrets.toml` 은 Git에 올리지 마세요 (이미 `.gitignore` 에 있음).

3. **구글 시트 공유**  
   사용할 스프레드시트를 `client_email`(서비스 계정 이메일)과 **편집자**로 공유해 두어야 합니다.

### 5. 앱 실행

```bash
streamlit run app.py
```

브라우저에서 **http://localhost:8501** 로 접속합니다.

- 종료: 터미널에서 `Ctrl+C`

---

## 한 번에 복사해서 쓰기 (요약)

```bash
cd attend-app
python3 -m venv venv
source venv/bin/activate          # Windows는 venv\Scripts\activate
pip install -r requirements.txt
mkdir -p .streamlit
# .streamlit/secrets.toml 에 GCP 서비스 계정 + encryption_key, default_password 넣기
streamlit run app.py
```
