import urllib.request
import urllib.parse
import json

url = "https://kauth.kakao.com/oauth/token"
data = {
    "grant_type": "authorization_code",
    "client_id": "2e2432752d3bcaaf637aa44cfb75a555",
    "redirect_uri": "http://localhost:3000",
    "code": "2hj1thcQgXWgjGKcGQaoMSV0sJNRIqN8kUlmSDywa7pIiNEJ-OkGhAAAAAQKDRlTAAABn8c1qhy2xj-RG-1vuA"
}

req_data = urllib.parse.urlencode(data).encode('utf-8')
req = urllib.request.Request(url, data=req_data)
response = urllib.request.urlopen(req)
result = json.loads(response.read().decode('utf-8'))
print("=== 새로 발급된 리프레시 토큰 ===")
print(result.get("refresh_token"))
